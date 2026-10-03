# ruff: noqa: E501
"""Does enforcing citations on every sentence work, and what does it cost in answer content?

Re-answers every question the model answered in evaluate_grounding.py (same index, same retrieval and
reranking, same top 3 passages), but with the strict prompt ("end every sentence with a citation") and
then drops any sentence that still has no valid citation (enforce_citations). It compares:

  baseline   the original reply from grounding_eval.json (default prompt, no enforcement)
  strict     the model's reply to the strict prompt, before enforcement
  enforced   the reply after enforce_citations (what a user would see)

Citation coverage is measured by counting sentences, and is about presence, not correctness: a
sentence can carry a citation to a passage that does not support it. The judge model (the same model
that wrote the answers, and shown to be unreliable in evaluate_grounding.py) re-checks the enforced
answers, and the answers it flags are printed so they can be read.

Needs the deployed Azure setup and a completed evaluate_grounding.py run (for the baseline):
    uv run --all-groups python capstone/evals/evaluate_citations.py
Finished questions are cached in citations_cache.json, so an interrupted run resumes.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Any

from evaluate_chunking import HERE, META_SECTIONS, load_documents, load_questions
from evaluate_grounding import (
    CANDIDATES,
    MAX_REQUESTS_PER_MINUTE,
    STRATEGY,
    TOP_K,
    TPM_BUDGET,
    Pacer,
    call_with_retries,
    citation_stats,
    estimate_tokens,
    judge,
    pct,
)

from payments_rag import (
    AzureChatGenerator,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    CrossEncoderReranker,
    GroundedAnswer,
    build_prompt,
    enforce_citations,
    rerank,
    strip_sections,
)

CACHE = HERE / "citations_cache.json"
BASELINE = HERE / "grounding_eval.json"


def coverage(stats: list[dict[str, Any]]) -> str:
    return pct(sum(s["sentences_cited"] for s in stats), sum(s["sentences"] for s in stats))


def main() -> None:
    settings = AzureSettings.from_env()
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings), AzureOpenAIEmbedder(settings), STRATEGY
    )
    reranker = CrossEncoderReranker()
    generator = AzureChatGenerator(settings)
    pacer = Pacer(TPM_BUDGET, MAX_REQUESTS_PER_MINUTE)
    cache: dict[str, Any] = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    baseline = {q["id"]: q for q in json.loads(BASELINE.read_text(encoding="utf-8"))["items"]}
    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    questions = {}
    for name in ("questions.json", "questions_heldout.json", "questions_abstain.json"):
        for q in load_questions(docs, HERE / name):
            questions[q["id"]] = q
    todo = [i for i, b in baseline.items() if not b["model_refused"]]
    print(f"{len(todo)} questions were answered in the baseline run", flush=True)

    rows: list[dict[str, Any]] = []
    for n, qid in enumerate(todo, 1):
        item = {**questions[qid], "answerable": bool(questions[qid]["gold"])}
        if qid in cache and cache[qid]["question"] == item["question"]:
            rows.append(cache[qid])
            print(f"{n:2d}/{len(todo)} {qid:>4} (cached)", flush=True)
            continue
        ranked = rerank(item["question"], retriever.search(item["question"], CANDIDATES), reranker)
        evidence = tuple(ranked[:TOP_K])
        answer = GroundedAnswer(item["question"], False, evidence, "strict citations")
        pacer.wait(estimate_tokens(build_prompt(answer, strict=True)))
        raw = call_with_retries(partial(generator.complete, build_prompt(answer, strict=True)))
        enforced = enforce_citations(raw, len(evidence))
        row: dict[str, Any] = {
            "id": qid,
            "question": item["question"],
            "answerable": item["answerable"],
            "baseline_reply": baseline[qid]["reply"],
            "baseline_stats": citation_stats(baseline[qid]["reply"], len(evidence)),
            "baseline_judgement": baseline[qid]["judgement"],
            "strict_reply": raw,
            "strict_stats": citation_stats(raw, len(evidence)),
            "enforced_reply": enforced.text,
            "enforced_stats": citation_stats(enforced.text, len(evidence)),
            "dropped": list(enforced.dropped),
            "invalid_markers": enforced.invalid_markers,
            "became_refusal": enforced.refused,
            "enforced_judgement": None,
        }
        if not enforced.refused:
            passages = "\n\n".join(f"[{i}] {h.chunk.text}" for i, h in enumerate(evidence, 1))
            row["enforced_judgement"] = judge(generator, pacer, item, passages, enforced.text)
        cache[qid] = row
        CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        rows.append(row)
        print(f"{n:2d}/{len(todo)} {qid:>4} dropped {len(row['dropped'])}", flush=True)

    answerable = [r for r in rows if r["answerable"]]
    unanswerable = [r for r in rows if not r["answerable"]]

    def words(key: str, subset: list[dict[str, Any]]) -> float:
        return sum(len(r[key].split()) for r in subset) / max(len(subset), 1)

    def correct(key: str, subset: list[dict[str, Any]]) -> int:
        return sum(bool((r[key] or {}).get("correct") is True) for r in subset)

    kept = [r for r in rows if not r["became_refusal"]]
    lines = [
        f"Re-answered {len(rows)} questions the model answered before (same index, retrieval, reranking and top-{TOP_K} passages).\n",
        "## 1. Citation coverage (share of sentences that carry a [n])\n",
        "| Reply | Sentences with a citation |",
        "|---|---|",
        f"| Baseline (default prompt) | {coverage([r['baseline_stats'] for r in rows])} |",
        f"| Strict prompt, before enforcement | {coverage([r['strict_stats'] for r in rows])} |",
        f"| After enforcement | {coverage([r['enforced_stats'] for r in kept])} (by construction) |",
        "",
        "## 2. What enforcement removed\n",
        f"- Sentences dropped for lacking a valid citation: {sum(len(r['dropped']) for r in rows)} across {sum(bool(r['dropped']) for r in rows)} answers.",
        f"- Citation markers removed because the passage number did not exist: {sum(r['invalid_markers'] for r in rows)}.",
        f"- Answers that became a refusal because no sentence had a valid citation: {sum(r['became_refusal'] for r in rows)}.",
        f"- Mean words per answer: baseline {words('baseline_reply', rows):.0f}, strict {words('strict_reply', rows):.0f}, enforced {words('enforced_reply', rows):.0f}.\n",
        "## 3. Did the content survive? (answerable questions; judge verdict, an unreliable one)\n",
        "| | Judged correct |",
        "|---|---|",
        f"| Baseline | {correct('baseline_judgement', answerable)}/{len(answerable)} |",
        f"| After enforcement | {correct('enforced_judgement', answerable)}/{len(answerable)} |",
        "",
        f"Of the {len(unanswerable)} unanswerable questions the model answered in the baseline run, "
        f"{sum(not r['became_refusal'] for r in unanswerable)} are still answered after enforcement.\n",
        "## 4. Answers to read (judge flags them, enforcement dropped sentences, or a correct answer turned into a refusal)\n",
    ]
    for r in rows:
        verdict = r["enforced_judgement"] or {}
        flagged = verdict.get("supported") is False or verdict.get("correct") is False
        lost = r["answerable"] and r["became_refusal"]
        if flagged or lost or r["dropped"]:
            lines += [
                f"- **{r['id']}** ({'answerable' if r['answerable'] else 'unanswerable'}): {r['question']}",
                f"  - enforced: {r['enforced_reply'][:260]}",
                f"  - dropped: {r['dropped'] or 'nothing'}",
                f"  - judge: supported={verdict.get('supported')}, correct={verdict.get('correct')}",
            ]
    text = "\n".join(lines) + "\n"
    (HERE / "citations_eval.md").write_text(text, encoding="utf-8")
    (HERE / "citations_eval.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
