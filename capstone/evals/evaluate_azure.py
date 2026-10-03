# ruff: noqa: E501
"""Rerun the dev and held-out questions through Azure OpenAI embeddings + Azure AI Search hybrid search.

Compares directly with the local hybrid result in embeddings_eval.md (same questions, same chunks).
Needs a deployed Azure setup:  uv run --all-groups python capstone/evals/evaluate_azure.py
It re-uploads the corpus to the search index first. Not yet run against live Azure.
"""

from __future__ import annotations

import json
import time

from evaluate_chunking import (
    HERE,
    META_SECTIONS,
    evaluate,
    load_documents,
    load_questions,
)

from payments_rag import (
    STRATEGIES,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    strip_sections,
)
from payments_rag.indexing import build_index

SPLITS = {
    "dev": HERE / "questions.json",
    "heldout": HERE / "questions_heldout.json",
    "corpus_update": HERE
    / "questions_corpus_update.json",  # the 2025 RBI document: only 5 answerable
}
if (
    HERE / "questions_independent.json"
).exists():  # questions taken from the web, not written by me
    SPLITS["independent"] = HERE / "questions_independent.json"


def main() -> None:
    settings = AzureSettings.from_env()
    embedder = AzureOpenAIEmbedder(settings)
    store = AzureSearchStore(settings)
    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    # The same code as `python -m payments_rag.indexing`: recreate the index, chunk, embed, upload,
    # and record which corpus the index holds.
    build_index(store=store, embedder=embedder)
    print("Uploaded; waiting 20 s for the index to refresh...", flush=True)
    time.sleep(20)

    results = {}
    for split, path in SPLITS.items():
        questions = load_questions(docs, path)
        results[split] = {
            s: evaluate(
                s,
                docs,
                questions,
                retriever_factory=lambda _chunks, s=s: AzureHybridRetriever(store, embedder, s),
            )
            for s in STRATEGIES
        }
        # The semantic ranker re-reads the top hybrid results with a language model. Scored for
        # structure-aware chunks only, to spare the free tier's monthly semantic-query allowance.
        results[split]["structure_aware+semantic"] = evaluate(
            "structure_aware",
            docs,
            questions,
            retriever_factory=lambda _chunks: AzureHybridRetriever(
                store, embedder, "structure_aware", semantic=True
            ),
        )

    lines = [
        "Azure OpenAI embeddings + Azure AI Search hybrid (keyword + vector, fused by Azure). "
        "Compare with the local hybrid in embeddings_eval.md.\n"
    ]
    for split, per_strategy in results.items():
        lines += [
            f"## {split}\n",
            "| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |",
            "|---|---|---|---|---|---|---|",
        ]
        for s, r in per_strategy.items():
            lines.append(
                f"| {s} | {r['hit@1']:.2f} | {r['hit@3']:.2f} | {r['hit@5']:.2f} | {r['mrr@10']:.2f} "
                f"| {r['hit@3_paraphrase']:.2f} | {r['query_ms_mean']} |"
            )
        lines.append("")
    text = "\n".join(lines)
    (HERE / "azure_eval.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (HERE / "azure_eval.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
