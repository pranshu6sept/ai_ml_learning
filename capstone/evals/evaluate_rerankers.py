# ruff: noqa: E501
"""Three ways to order the same candidates: hybrid search alone, hybrid + the local cross-encoder, and
hybrid + Azure's semantic ranker.

All three start from the same Azure hybrid search over structure-aware chunks (the index built by
`python -m payments_rag.indexing`) and are scored on the same questions with the same metrics:

  hybrid            Azure keyword + vector search, fused by Azure;
  + local rerank    the top 10 hybrid results re-scored by the local ms-marco cross-encoder
                    (the reranker used by the grounding pipeline);
  + semantic        Azure's semantic ranker (needs the semantic configuration on the index).

Run after the index exists:
    uv run --all-groups python capstone/evals/evaluate_rerankers.py
Needs a signed-in `az login`. Uses the free tier's monthly semantic-query allowance (about 180 queries).
"""

from __future__ import annotations

import json

from evaluate_azure import SPLITS
from evaluate_chunking import HERE, META_SECTIONS, evaluate, load_documents, load_questions

from payments_rag import (
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    CrossEncoderReranker,
    Hit,
    rerank,
    strip_sections,
)

STRATEGY = "structure_aware"
CANDIDATES = 10


class LocallyReranked:
    """Hybrid search, then the local cross-encoder re-scores the top candidates."""

    def __init__(self, hybrid: AzureHybridRetriever, reranker: CrossEncoderReranker) -> None:
        self._hybrid = hybrid
        self._reranker = reranker

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        candidates = self._hybrid.search(query, CANDIDATES)
        return rerank(query, candidates, self._reranker)[:top_k]


def main() -> None:
    settings = AzureSettings.from_env()
    embedder = AzureOpenAIEmbedder(settings)
    store = AzureSearchStore(settings)
    reranker = CrossEncoderReranker()
    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}

    variants = {
        "hybrid": lambda _c: AzureHybridRetriever(store, embedder, STRATEGY),
        "hybrid + local cross-encoder": lambda _c: LocallyReranked(
            AzureHybridRetriever(store, embedder, STRATEGY), reranker
        ),
        "hybrid + Azure semantic ranker": lambda _c: AzureHybridRetriever(
            store, embedder, STRATEGY, semantic=True
        ),
    }
    results: dict[str, dict[str, dict]] = {}
    for split, path in SPLITS.items():
        questions = load_questions(docs, path)
        n = sum(bool(q["gold"]) for q in questions)
        results[split] = {
            name: evaluate(STRATEGY, docs, questions, retriever_factory=factory)
            for name, factory in variants.items()
        }
        results[split]["_answerable"] = n  # type: ignore[assignment]

    lines = [
        "Structure-aware chunks, one Azure index, three ways to order the candidates. "
        "One question is worth 1 divided by the number of answerable questions.\n"
    ]
    for split, per_variant in results.items():
        n = per_variant.pop("_answerable")
        lines += [
            f"## {split} ({n} answerable)\n",
            "| Ordering | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Query (ms) |",
            "|---|---|---|---|---|---|",
        ]
        for name, r in per_variant.items():
            lines.append(
                f"| {name} | {r['hit@1']:.2f} | {r['hit@3']:.2f} | {r['hit@5']:.2f} | {r['mrr@10']:.2f} | {r['query_ms_mean']} |"
            )
        lines.append("")
    text = "\n".join(lines)
    (HERE / "rerankers_eval.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (HERE / "rerankers_eval.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
