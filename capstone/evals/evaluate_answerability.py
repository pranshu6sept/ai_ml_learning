# ruff: noqa: E501
"""Is a quote-verified answerability check a better "should we answer?" signal than the reranker score?

For every question (retrieval, reranking and top-3 passages exactly as in evaluate_grounding.py) a
language model is asked whether the passages state the answer and to copy one sentence that does.
Code then checks that the quote really appears in a passage (payments_rag.grounding.Answerability).
The question is answered only if the label is "full" AND the quote is found. Compared with the
reranker score and the threshold tuned in evaluate_grounding.py.

Honest limits, printed in the report: u03 and b03 were the two failures seen before this check was
written, so results on them are not independent evidence (the report also gives results without
them); the check needs no tuned threshold, which avoids tune/test leakage but means it is a yes/no
signal; the questions are the author's.

Needs the deployed Azure setup and a completed evaluate_grounding.py run:
    uv run --all-groups python capstone/evals/evaluate_answerability.py
Finished questions are cached in answerability_cache.json, so an interrupted run resumes.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Any

import numpy as np
from evaluate_chunking import HERE, META_SECTIONS, is_relevant, load_documents, load_questions
from evaluate_grounding import (
    CANDIDATES,
    MAX_REQUESTS_PER_MINUTE,
    STRATEGY,
    TOP_K,
    TPM_BUDGET,
    Pacer,
    call_with_retries,
    estimate_tokens,
    pct,
)
from sklearn.metrics import roc_auc_score

from payments_rag import (
    AzureChatGenerator,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    CrossEncoderReranker,
    answerability_prompt,
    parse_answerability,
    rerank,
    strip_sections,
)

CACHE = HERE / "answerability_cache.json"
GROUNDING = HERE / "grounding_eval.json"
SEEN_BEFORE_WRITING_THE_CHECK = {"u03", "b03"}
LABEL_SCORE = {"full": 2.0, "partial": 1.0, "none": 0.0}


def auroc(items: list[dict[str, Any]], key: str) -> str:
    labels = [int(q["answerable"]) for q in items]
    if len(set(labels)) < 2:
        return "n/a"
    return f"{roc_auc_score(labels, [q[key] for q in items]):.2f}"


def gate_table(items: list[dict[str, Any]], decide: str) -> str:
    ans = [q for q in items if q["answerable"]]
    una = [q for q in items if not q["answerable"]]
    answered = [q for q in ans if q[decide]]
    shipped = [q for q in una if q[decide]]
    return (
        f"{len(answered)}/{len(ans)} answerable answered ({pct(sum(q['evidence_has_answer'] for q in answered), len(answered))} with the "
        f"answer in the passages) | {len(ans) - len(answered)} wrongly refused | "
        f"{len(una) - len(shipped)}/{len(una)} unanswerable refused | {len(shipped)} wrong answers shipped"
    )


def main() -> None:
    settings = AzureSettings.from_env()
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings), AzureOpenAIEmbedder(settings), STRATEGY
    )
    reranker = CrossEncoderReranker()
    generator = AzureChatGenerator(settings)
    pacer = Pacer(TPM_BUDGET, MAX_REQUESTS_PER_MINUTE)
    cache: dict[str, Any] = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    threshold = json.loads(GROUNDING.read_text(encoding="utf-8"))["threshold"]

    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    items: list[dict[str, Any]] = []
    for split, name in (("tune", "questions.json"), ("test", "questions_heldout.json")):
        items += [{**q, "split": split} for q in load_questions(docs, HERE / name)]
    items += load_questions(docs, HERE / "questions_abstain.json")
    for q in items:
        q["answerable"] = bool(q["gold"])

    for n, item in enumerate(items, 1):
        saved = cache.get(item["id"])
        if saved and saved["question"] == item["question"]:
            item.update(saved["fields"])
            print(f"{n:2d}/{len(items)} {item['id']:>4} (cached)", flush=True)
            continue
        ranked = rerank(item["question"], retriever.search(item["question"], CANDIDATES), reranker)
        evidence = tuple(ranked[:TOP_K])
        item["top_score"] = ranked[0].score if ranked else -20.0
        item["evidence_has_answer"] = item["answerable"] and any(
            is_relevant(h.chunk, item) for h in evidence
        )
        if evidence:
            prompt = answerability_prompt(item["question"], evidence)
            pacer.wait(estimate_tokens(prompt))
            raw = call_with_retries(partial(generator.complete, prompt, json_mode=True))
            check = parse_answerability(raw, evidence)
        else:
            check = parse_answerability("", evidence)
        item.update(
            label=check.label,
            quote=check.quote,
            quote_found=check.quote_found,
            can_answer=check.can_answer,
        )
        fields = {
            k: item[k]
            for k in (
                "top_score",
                "evidence_has_answer",
                "label",
                "quote",
                "quote_found",
                "can_answer",
            )
        }
        cache[item["id"]] = {"question": item["question"], "fields": fields}
        CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        print(
            f"{n:2d}/{len(items)} {item['id']:>4} {check.label:>7} quote_found={check.quote_found}",
            flush=True,
        )

    for q in items:
        q["label_score"] = LABEL_SCORE[q["label"]]
        q["verified_score"] = float(q["can_answer"])
        q["combined_score"] = q["verified_score"] * 100 + q["top_score"]
        q["reranker_gate"] = q["top_score"] >= threshold
    rest = [q for q in items if q["id"] not in SEEN_BEFORE_WRITING_THE_CHECK]

    lines = [
        f"{len(items)} questions ({sum(q['answerable'] for q in items)} answerable, {sum(not q['answerable'] for q in items)} unanswerable), "
        f"same retrieval, reranking and top-{TOP_K} passages as evaluate_grounding.py. Reranker gate threshold: {threshold:.2f} (tuned there on the tune set).\n",
        "## 1. How well does each signal separate answerable from unanswerable? (AUROC; 1.0 perfect, 0.5 chance)\n",
        "| Signal | All 80 | Without u03 and b03 (seen before the check was written) |",
        "|---|---|---|",
        f"| Reranker score | {auroc(items, 'top_score')} | {auroc(rest, 'top_score')} |",
        f"| Model's label (full=2, partial=1, none=0) | {auroc(items, 'label_score')} | {auroc(rest, 'label_score')} |",
        f"| Label full AND quote verified (yes/no) | {auroc(items, 'verified_score')} | {auroc(rest, 'verified_score')} |",
        f"| Verified yes/no, ties broken by reranker score | {auroc(items, 'combined_score')} | {auroc(rest, 'combined_score')} |",
        "",
        "## 2. As a gate (what a user would see)\n",
        f"- **Reranker gate (4.41)**, all 80: {gate_table(items, 'reranker_gate')}",
        f"- **Reranker gate**, without u03 and b03: {gate_table(rest, 'reranker_gate')}",
        f"- **Quote-verified check**, all 80: {gate_table(items, 'can_answer')}",
        f"- **Quote-verified check**, without u03 and b03: {gate_table(rest, 'can_answer')}",
        "",
        "## 3. How often does the model make up a quote?\n",
        f'- Said "full": {sum(q["label"] == "full" for q in items)} questions. Of those, the quote was NOT found in the passages: {sum(q["label"] == "full" and not q["quote_found"] for q in items)}.',
        f"- Labels given: full {sum(q['label'] == 'full' for q in items)}, partial {sum(q['label'] == 'partial' for q in items)}, none {sum(q['label'] == 'none' for q in items)}.",
        "",
        "## 4. The two failures seen earlier, and every disagreement between the two gates\n",
    ]
    for q in items:
        if q["id"] in SEEN_BEFORE_WRITING_THE_CHECK or q["can_answer"] != q["reranker_gate"]:
            kind = "answerable" if q["answerable"] else "UNANSWERABLE"
            lines += [
                f"- **{q['id']}** ({kind}, evidence has answer: {q['evidence_has_answer']}): {q['question']}",
                f"  - reranker {q['top_score']:.2f} ({'answer' if q['reranker_gate'] else 'refuse'}); model label {q['label']}, quote found {q['quote_found']} ({'answer' if q['can_answer'] else 'refuse'})",
                f"  - quote: {q['quote'][:200] or '(none)'}",
            ]
    text = "\n".join(lines) + "\n"
    (HERE / "answerability_eval.md").write_text(text, encoding="utf-8")
    (HERE / "answerability_eval.json").write_text(
        json.dumps(
            [{k: v for k, v in q.items() if k != "gold"} for q in items], indent=2, default=float
        ),
        encoding="utf-8",
    )
    print(text)
    _ = np  # numpy is used by sklearn; keep the import explicit for type checkers


if __name__ == "__main__":
    main()
