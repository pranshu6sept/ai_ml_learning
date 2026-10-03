"""Can the system tell when it should NOT answer? Compare signals, tuning on one set, judging on another.

Signals: top BM25 score, top embedding similarity, top hybrid score, top cross-encoder reranker score.
A threshold is chosen on the tune set (dev questions plus the first half of the abstention questions)
and applied unchanged to the test set (held-out questions plus the second half). Everything about the
setup (models, hybrid constant, reranker, 10 candidates) was fixed before looking at results.

Needs the embeddings dependency group.
Run from the repo root:  uv run python capstone/evals/evaluate_abstention.py
"""

# ruff: noqa: E501
from __future__ import annotations

import json
from typing import Any

import numpy as np
from evaluate_chunking import (
    HERE,
    META_SECTIONS,
    chunk_corpus,
    is_relevant,
    load_documents,
    load_questions,
)
from sklearn.metrics import roc_auc_score

from payments_rag import (
    CrossEncoderReranker,
    Retriever,
    SentenceTransformerEmbedder,
    choose_threshold,
    rerank,
    strip_sections,
)

CANDIDATES = 10
NO_SCORE = -20.0  # used when nothing was retrieved at all
SIGNALS = ["bm25", "embedding", "hybrid", "reranker"]


def top_score(retriever: Retriever, text: str) -> float:
    hits = retriever.search(text, 1)
    return hits[0].score if hits else 0.0


def main() -> None:
    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    dev = load_questions(docs, HERE / "questions.json")
    heldout = load_questions(docs, HERE / "questions_heldout.json")
    abstain = load_questions(docs, HERE / "questions_abstain.json")

    items: list[dict[str, Any]] = []
    for q in dev:
        items.append(
            {
                **q,
                "split": "tune",
                "subtype": q.get("subtype", "answerable" if q["gold"] else "hard"),
            }
        )
    for q in heldout:
        items.append(
            {
                **q,
                "split": "test",
                "subtype": q.get("subtype", "answerable" if q["gold"] else "hard"),
            }
        )
    items += abstain
    for q in items:
        q["answerable"] = bool(q["gold"])

    embedder = SentenceTransformerEmbedder()
    reranker = CrossEncoderReranker()
    chunks = chunk_corpus(docs, "structure_aware")
    bm25 = Retriever(chunks, method="bm25", stem=True)
    emb = Retriever(chunks, method="embedding", embedder=embedder)
    hybrid = Retriever(chunks, method="hybrid", stem=True, embedder=embedder)

    ranks: dict[str, dict[str, int]] = {"hybrid": {}, "reranker": {}}
    for q in items:
        text = q["question"]
        candidates = hybrid.search(text, CANDIDATES)
        ranked = rerank(text, candidates, reranker)
        q["scores"] = {
            "bm25": top_score(bm25, text),
            "embedding": top_score(emb, text),
            "hybrid": candidates[0].score if candidates else 0.0,
            "reranker": ranked[0].score if ranked else NO_SCORE,
        }
        q["top_reranked"] = ranked[0].chunk.section if ranked else None
        if q["answerable"]:
            for name, hits in (("hybrid", candidates), ("reranker", ranked)):
                ranks[name][q["id"]] = next(
                    (i for i, h in enumerate(hits, 1) if is_relevant(h.chunk, q)), 0
                )

    def arr(split: str | None, name: str, answerable: bool, hard_only: bool = False) -> list[float]:
        return [
            q["scores"][name]
            for q in items
            if q["answerable"] == answerable
            and (split is None or q["split"] == split)
            and not (hard_only and q["subtype"] == "off_topic")
        ]

    def auroc(split: str | None, name: str, hard_only: bool = False) -> float:
        pos, neg = arr(split, name, True, hard_only), arr(split, name, False, hard_only)
        return float(roc_auc_score([1] * len(pos) + [0] * len(neg), pos + neg))

    sizes = {
        s: (
            sum(q["answerable"] for q in items if q["split"] == s),
            sum(not q["answerable"] for q in items if q["split"] == s),
        )
        for s in ("tune", "test")
    }
    out = [
        "Structure-aware chunks, hybrid candidates (top 10), cross-encoder ms-marco-MiniLM-L-6-v2. "
        "Nothing tuned except the threshold, which is chosen on the tune set only.\n",
        f"Tune set: {sizes['tune'][0]} answerable, {sizes['tune'][1]} unanswerable. "
        f"Test set: {sizes['test'][0]} answerable, {sizes['test'][1]} unanswerable "
        f"({sum(q['subtype'] == 'off_topic' for q in items if q['split'] == 'test')} of them off-topic).\n",
        "## How well does each score separate answerable from unanswerable? (AUROC)\n",
        "1.0 is perfect, 0.5 is chance. 'Hard only' leaves out the off-topic questions.\n",
        "| Signal | Tune | Test | All | All, hard only |",
        "|---|---|---|---|---|",
    ]
    for name in SIGNALS:
        out.append(
            f"| {name} | {auroc('tune', name):.2f} | {auroc('test', name):.2f} "
            f"| {auroc(None, name):.2f} | {auroc(None, name, True):.2f} |"
        )

    out += [
        "\n## Threshold chosen on the tune set, applied unchanged to the test set\n",
        "| Signal | Threshold | Tune: answered / refused | Test: answered | Test: refused (hard) "
        "| Test: refused (off-topic) | Test balanced accuracy |",
        "|---|---|---|---|---|---|---|",
    ]
    thresholds = {}
    for name in SIGNALS:
        t = choose_threshold(arr("tune", name, True), arr("tune", name, False))
        thresholds[name] = t
        tune_a = np.mean(np.asarray(arr("tune", name, True)) >= t)
        tune_u = np.mean(np.asarray(arr("tune", name, False)) < t)
        test_items = [q for q in items if q["split"] == "test"]
        ans = [q["scores"][name] >= t for q in test_items if q["answerable"]]
        hard = [
            q["scores"][name] < t
            for q in test_items
            if not q["answerable"] and q["subtype"] == "hard"
        ]
        off = [q["scores"][name] < t for q in test_items if q["subtype"] == "off_topic"]
        bal = (np.mean(ans) + np.mean(hard + off)) / 2
        out.append(
            f"| {name} | {t:.3g} | {tune_a:.2f} / {tune_u:.2f} | {np.mean(ans):.2f} ({sum(ans)}/{len(ans)}) "
            f"| {np.mean(hard):.2f} ({sum(hard)}/{len(hard)}) | {np.mean(off):.2f} ({sum(off)}/{len(off)}) "
            f"| {bal:.2f} |"
        )

    out += [
        "\n## The trade-off: refusing more unanswerable questions also refuses more answerable ones\n",
        "Descriptive only (all questions pooled, nothing tuned): for each target share of unanswerable "
        "questions refused, the share of answerable questions still answered.\n",
        "| Refuse this share of unanswerable | Reranker: answerable still answered | "
        "Embedding: answerable still answered |",
        "|---|---|---|",
    ]
    for share in (1.0, 0.9, 0.8, 0.7):
        cells = []
        for name in ("reranker", "embedding"):
            neg = np.sort(np.asarray(arr(None, name, False)))
            cut = (
                neg[-1] + 1e-9 if share == 1.0 else np.quantile(neg, share, method="higher") + 1e-9
            )
            pos = np.asarray(arr(None, name, True))
            cells.append(f"{np.mean(pos >= cut):.2f}")
        out.append(f"| {share:.0%} | {cells[0]} | {cells[1]} |")

    out += [
        "\n## Does reranking improve which chunk comes first? (answerable questions)\n",
        "| Set | Ordering | Hit@1 | Hit@3 |",
        "|---|---|---|---|",
    ]
    for label, split in (("Dev", "tune"), ("Held-out", "test")):
        ids = [q["id"] for q in items if q["answerable"] and q["split"] == split]
        for name, title in (("hybrid", "hybrid (before)"), ("reranker", "reranked")):
            r = [ranks[name][i] for i in ids]
            out.append(
                f"| {label} ({len(ids)}) | {title} | {np.mean([0 < x <= 1 for x in r]):.2f} "
                f"| {np.mean([0 < x <= 3 for x in r]):.2f} |"
            )

    t = thresholds["reranker"]
    wrong_refusals = [
        q for q in items if q["split"] == "test" and q["answerable"] and q["scores"]["reranker"] < t
    ]
    wrong_answers = [
        q
        for q in items
        if q["split"] == "test" and not q["answerable"] and q["scores"]["reranker"] >= t
    ]
    out.append(f"\n## Test-set mistakes with the reranker threshold ({t:.3g})\n")
    for title, group in (
        ("Answerable but refused", wrong_refusals),
        ("Unanswerable but answered", wrong_answers),
    ):
        out.append(f"**{title}: {len(group)}**\n")
        out += [f"- {q['id']} ({q['scores']['reranker']:.2f}): {q['question']}" for q in group] or [
            "- none"
        ]
        out.append("")

    text = "\n".join(out) + "\n"
    (HERE / "abstention_eval.json").write_text(
        json.dumps({"thresholds": thresholds, "questions": items}, indent=2, default=float),
        encoding="utf-8",
    )
    (HERE / "abstention_eval.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
