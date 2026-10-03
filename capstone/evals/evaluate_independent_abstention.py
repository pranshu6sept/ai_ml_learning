# ruff: noqa: E501
"""Do the abstain signals still work on questions I did not write? (questions_independent.json)

The independent questions are real question titles taken from Quora and the PCI SSC FAQ page, in the order a
search returned them. Only about a fifth can be answered from the corpus (9 of 44), and that share is itself
a finding. For each question this runs the same pipeline as evaluate_answerability.py (Azure hybrid
retrieval, local reranker, top 3 passages) and compares two gates:

  reranker gate     answer if the best reranked passage scores at least the threshold tuned in
                    evaluate_grounding.py (4.41 on the author's tune questions);
  quote-verified    answer only if the model says "full" and its quote is found in the passages.

Nothing is tuned here: the threshold and the prompt were fixed before these questions existed.

Needs the deployed Azure setup and a completed evaluate_grounding.py run:
    uv run --all-groups python capstone/evals/evaluate_independent_abstention.py
Finished questions are cached in independent_cache.json, so an interrupted run resumes.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Any

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

CACHE = HERE / "independent_cache.json"
LABEL_SCORE = {"full": 2.0, "partial": 1.0, "none": 0.0}


def main() -> None:
    settings = AzureSettings.from_env()
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings), AzureOpenAIEmbedder(settings), STRATEGY
    )
    reranker = CrossEncoderReranker()
    generator = AzureChatGenerator(settings)
    pacer = Pacer(TPM_BUDGET, MAX_REQUESTS_PER_MINUTE)
    cache: dict[str, Any] = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    threshold = json.loads((HERE / "grounding_eval.json").read_text(encoding="utf-8"))["threshold"]

    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    items = load_questions(docs, HERE / "questions_independent.json")
    for q in items:
        q["answerable"] = bool(q["gold"])

    for n, item in enumerate(items, 1):
        saved = cache.get(item["id"])
        if saved and saved["question"] == item["question"]:
            item.update(saved["fields"])
            continue
        ranked = rerank(item["question"], retriever.search(item["question"], CANDIDATES), reranker)
        evidence = tuple(ranked[:TOP_K])
        item["top_score"] = ranked[0].score if ranked else -20.0
        item["evidence_has_answer"] = item["answerable"] and any(
            is_relevant(h.chunk, item) for h in evidence
        )
        item["top_section"] = (
            f"{evidence[0].chunk.doc_id} > {evidence[0].chunk.section}" if evidence else ""
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
        keys = (
            "top_score",
            "evidence_has_answer",
            "top_section",
            "label",
            "quote",
            "quote_found",
            "can_answer",
        )
        cache[item["id"]] = {"question": item["question"], "fields": {k: item[k] for k in keys}}
        CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        print(
            f"{n:2d}/{len(items)} {item['id']:>5} {check.label:>7} reranker {item['top_score']:6.2f}",
            flush=True,
        )

    for q in items:
        q["reranker_gate"] = q["top_score"] >= threshold
    ans = [q for q in items if q["answerable"]]
    una = [q for q in items if not q["answerable"]]
    y = [int(q["answerable"]) for q in items]

    def gate(key: str) -> str:
        answered = [q for q in ans if q[key]]
        shipped = [q for q in una if q[key]]
        return (
            f"{len(answered)}/{len(ans)} answerable answered ({sum(q['evidence_has_answer'] for q in answered)} with the answer in the passages) | "
            f"{len(ans) - len(answered)} wrongly refused | {len(una) - len(shipped)}/{len(una)} unanswerable refused | "
            f"{len(shipped)} wrong answers shipped"
        )

    lines = [
        f"{len(items)} independent questions ({len(ans)} answerable from the corpus, {len(una)} not), taken from Quora titles and the "
        f"PCI SSC FAQ page in search order. Reranker gate threshold {threshold:.2f} was fixed on the author's own questions.\n",
        "## 1. How well does each signal separate answerable from unanswerable? (AUROC, 1.0 perfect, 0.5 chance)\n",
        "| Signal | AUROC |",
        "|---|---|",
        f"| Reranker score | {roc_auc_score(y, [q['top_score'] for q in items]):.2f} |",
        f"| Model's label (full=2, partial=1, none=0) | {roc_auc_score(y, [LABEL_SCORE[q['label']] for q in items]):.2f} |",
        f"| Label full AND quote verified (yes/no) | {roc_auc_score(y, [float(q['can_answer']) for q in items]):.2f} |",
        "",
        "## 2. As a gate\n",
        f"- **Reranker gate ({threshold:.2f})**: {gate('reranker_gate')}",
        f"- **Quote-verified check**: {gate('can_answer')}",
        f'- Quotes the model made up (said "full", quote not in the passages): {sum(q["label"] == "full" and not q["quote_found"] for q in items)}',
        "",
        "## 3. Every answerable question, and every unanswerable one a gate would have answered\n",
    ]
    for q in items:
        if q["answerable"] or q["reranker_gate"] or q["can_answer"]:
            kind = "answerable" if q["answerable"] else "UNANSWERABLE"
            lines += [
                f"- **{q['id']}** ({kind}): {q['question'][:150]}",
                f"  - reranker {q['top_score']:.2f} ({'answer' if q['reranker_gate'] else 'refuse'}); label {q['label']}, quote found {q['quote_found']} ({'answer' if q['can_answer'] else 'refuse'}); evidence has the answer: {q['evidence_has_answer']}",
                f"  - top passage: {q['top_section'][:110]}",
            ]
            if q["can_answer"]:
                lines.append(f"  - quote: {q['quote'][:200]}")
    text = "\n".join(lines) + "\n"
    (HERE / "independent_abstention_eval.md").write_text(text, encoding="utf-8")
    (HERE / "independent_abstention_eval.json").write_text(
        json.dumps(
            [{k: v for k, v in q.items() if k != "gold"} for q in items], indent=2, default=float
        ),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
