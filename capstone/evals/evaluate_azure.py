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
    chunk_corpus,
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

SPLITS = {
    "dev": HERE / "questions.json",
    "heldout": HERE / "questions_heldout.json",
    "corpus_update": HERE
    / "questions_corpus_update.json",  # the 2025 RBI document: only 5 answerable
}


def main() -> None:
    settings = AzureSettings.from_env()
    embedder = AzureOpenAIEmbedder(settings)
    store = AzureSearchStore(settings)
    store.recreate_index()  # clean rebuild: upserts would leave stale chunks of changed documents

    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    for strategy in STRATEGIES:
        chunks = chunk_corpus(docs, strategy)
        store.upload(chunks, embedder([c.text for c in chunks]))
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
