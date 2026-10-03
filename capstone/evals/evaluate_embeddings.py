"""Compare lexical, embedding and hybrid retrieval on the dev and held-out questions.

Choices fixed before looking at results: the embedding model is all-MiniLM-L6-v2 (the common
default), hybrid is reciprocal rank fusion of BM25+stemming and the embeddings with the standard
constant 60, and nothing is tuned. The held-out questions were written before any retrieval change.

Needs the embeddings dependency group: ``uv sync --group embeddings``.
Run from the repo root:  uv run python capstone/evals/evaluate_embeddings.py
"""

from __future__ import annotations

import json
from typing import Any

from evaluate_chunking import (
    HERE,
    META_SECTIONS,
    chunk_corpus,
    evaluate,
    load_documents,
    load_questions,
)
from sklearn.metrics import roc_auc_score

from payments_rag import STRATEGIES, Retriever, SentenceTransformerEmbedder, strip_sections

SPLITS = {"dev": HERE / "questions.json", "heldout": HERE / "questions_heldout.json"}


def main() -> None:
    embedder = SentenceTransformerEmbedder()
    retrievers: dict[str, dict[str, Any]] = {
        "tfidf (baseline)": {},
        "bm25+stem": {"method": "bm25", "stem": True},
        "embedding": {"method": "embedding", "embedder": embedder},
        "hybrid (bm25+stem, embedding)": {"method": "hybrid", "stem": True, "embedder": embedder},
    }
    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    questions = {split: load_questions(docs, path) for split, path in SPLITS.items()}

    results = {
        split: {
            name: {s: evaluate(s, docs, qs, opts) for s in STRATEGIES}
            for name, opts in retrievers.items()
        }
        for split, qs in questions.items()
    }

    base = results["dev"]["tfidf (baseline)"]
    hard = sorted(
        set.intersection(
            *({m["id"] for m in base[s]["missed_or_below_rank_3"]} for s in STRATEGIES)
        )
    )

    # Can the top score tell answerable from unanswerable? (structure_aware chunks, both splits)
    chunks = chunk_corpus(docs, "structure_aware")
    all_questions = [q for qs in questions.values() for q in qs]
    labels = [int(bool(q["gold"])) for q in all_questions]
    auroc = {}
    for name, opts in retrievers.items():
        index = Retriever(chunks, **opts)
        tops = [
            (h[0].score if (h := index.search(q["question"], 1)) else 0.0) for q in all_questions
        ]
        auroc[name] = roc_auc_score(labels, tops)

    def table(split: str) -> str:
        rows = [
            "| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased "
            "| Query (ms) |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for name in retrievers:
            for s in STRATEGIES:
                r = results[split][name][s]
                rows.append(
                    f"| {name} | {s} | {r['hit@1']:.2f} | {r['hit@3']:.2f} | {r['hit@5']:.2f} "
                    f"| {r['mrr@10']:.2f} | {r['hit@3_paraphrase']:.2f} | {r['query_ms_mean']} |"
                )
        return "\n".join(rows) + "\n"

    recovered = [
        f"| Retrieval | Strategy | Hard questions in the top 3 (of {len(hard)}) |",
        "|---|---|---|",
    ]
    for name in retrievers:
        for s in STRATEGIES:
            missed = {m["id"] for m in results["dev"][name][s]["missed_or_below_rank_3"]}
            found = [q for q in hard if q not in missed]
            recovered.append(f"| {name} | {s} | {len(found)} ({', '.join(found) or 'none'}) |")

    n = {sp: sum(bool(q["gold"]) for q in qs) for sp, qs in questions.items()}
    unans = sum(1 - label for label in labels)
    text = (
        "Embedding model: all-MiniLM-L6-v2 (local, 384 dimensions). Hybrid = "
        "reciprocal rank fusion "
        "(constant 60) of BM25 with stemming and the embeddings. Nothing tuned. Meta sections "
        "removed; "
        "chunks about 80 words.\n\n"
        f"## Dev set ({n['dev']} answerable)\n\n{table('dev')}\n"
        f"## Held-out set ({n['heldout']} answerable; one question = {1 / n['heldout']:.3f})\n\n"
        f"Written before any retrieval change.\n\n{table('heldout')}\n"
        "## Dev questions every strategy missed with plain TF-IDF\n\n"
        + "\n".join(recovered)
        + "\n\n"
        f"## Can the top score separate answerable from unanswerable? "
        f"(AUROC, structure_aware chunks, {sum(labels)} answerable vs {unans} unanswerable)\n\n"
        "1.0 means every answerable question scored above every unanswerable one; 0.5 is no "
        "better than "
        "chance.\n\n| Retrieval | AUROC |\n|---|---|\n"
        + "\n".join(f"| {name} | {value:.2f} |" for name, value in auroc.items())
        + "\n"
    )
    (HERE / "embeddings_eval.json").write_text(
        json.dumps({"results": results, "auroc": auroc}, indent=2), encoding="utf-8"
    )
    (HERE / "embeddings_eval.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
