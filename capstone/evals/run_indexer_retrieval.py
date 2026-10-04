# ruff: noqa: E501
"""Push pipeline vs the Azure-managed indexer pipeline: same golden set, same hybrid search.

Three indexes are scored on the 69 answerable golden questions, all with keyword + vector hybrid search
and no semantic ranker (the Basic service has it disabled), so only the chunking and indexing differ:

* push, fixed chunks         our `fixed` chunker (80 words, 20 overlap), uploaded by `payments_rag.indexing`
* push, structure-aware      our heading-aware chunker, same upload path (the best setting from Week 5)
* indexer (Text Split)       the Blob -> indexer -> skillset pipeline of `blob_indexing.py`, pages of 600 characters

It also reports, for each chunking, how many questions have their gold phrase intact inside one chunk
(a phrase cut in half by a chunk boundary cannot be retrieved at all).

    uv run --all-groups python capstone/evals/run_indexer_retrieval.py

Needs `az login`, both search services, and the indexer already run (`run_blob_indexer.py`).
Writes `results/indexer_vs_push.md|json`.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from evaluate_chunking import HERE, META_SECTIONS, evaluate, is_relevant, load_documents
from run_retrieval import METRICS, RESULTS, load_golden

from payments_rag import (
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    Hit,
    strip_sections,
)
from payments_rag.azure_clients import read_dotenv
from payments_rag.chunking import Chunk

ENV = HERE.parents[1] / ".env"
INDEX = "payments-blob-index"


class IndexerRetriever:
    """Hybrid search (keyword + vector) over the indexer-built index."""

    def __init__(self, client: Any, embedder: AzureOpenAIEmbedder) -> None:
        self._client = client
        self._embedder = embedder

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        from azure.search.documents.models import VectorizedQuery

        vector = [float(x) for x in self._embedder([query])[0]]
        rows = self._client.search(
            search_text=query,
            vector_queries=[
                VectorizedQuery(vector=vector, k_nearest_neighbors=max(top_k, 50), fields="vector")
            ],
            select=["id", "doc_id", "text"],
            top=top_k,
        )
        return [
            Hit(
                Chunk(r["text"], i, doc_id=str(r["doc_id"]).removesuffix(".md")),
                float(r["@search.score"]),
            )
            for i, r in enumerate(rows)
        ]


def all_chunks(client: Any) -> list[Chunk]:
    rows = client.search(search_text="*", select=["id", "doc_id", "text"], top=1000)
    return [
        Chunk(r["text"], i, doc_id=str(r["doc_id"]).removesuffix(".md")) for i, r in enumerate(rows)
    ]


def main() -> None:
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    values = read_dotenv(ENV)
    settings = AzureSettings.from_env()
    embedder = AzureOpenAIEmbedder(settings)
    store = AzureSearchStore(settings)
    indexer_client = SearchClient(
        values["AZURE_W7_SEARCH_ENDPOINT"], INDEX, DefaultAzureCredential()
    )

    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = [q for q in load_golden(documents) if q["expected"] == "answer"]

    variants = {
        "push, fixed chunks": lambda _c: AzureHybridRetriever(store, embedder, "fixed"),
        "push, structure-aware chunks": lambda _c: AzureHybridRetriever(
            store, embedder, "structure_aware"
        ),
        "indexer (Text Split, 600 chars)": lambda _c: IndexerRetriever(indexer_client, embedder),
    }
    results = {
        name: evaluate("structure_aware", documents, golden, retriever_factory=f)
        for name, f in variants.items()
    }

    indexer_chunks = all_chunks(indexer_client)
    intact = sum(any(is_relevant(c, q) for c in indexer_chunks) for q in golden)
    sizes = sorted(len(c.text) for c in indexer_chunks)

    lines = [
        f"{len(golden)} answerable golden questions. Same hybrid search (keyword + vector, no semantic ranker) over three indexes. One question is worth {1 / len(golden):.3f}.\n",
        "| Index | Chunks | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    chunk_counts = {
        "push, fixed chunks": 52,
        "push, structure-aware chunks": 63,
        "indexer (Text Split, 600 chars)": len(indexer_chunks),
    }
    for name, r in results.items():
        lines.append(
            f"| {name} | {chunk_counts[name]} | "
            + " | ".join(f"{r[m]:.2f}" for m in METRICS)
            + " |"
        )
    lines += [
        "",
        f"Indexer chunks: {len(indexer_chunks)} pages, {sizes[0]} to {sizes[-1]} characters (median {sizes[len(sizes) // 2]}). "
        f"Gold phrase intact inside one indexer chunk for {intact} of {len(golden)} questions.\n",
    ]
    text = "\n".join(lines)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "indexer_vs_push.md").write_text(text, encoding="utf-8")
    (RESULTS / "indexer_vs_push.json").write_text(
        json.dumps(
            {
                "results": {k: {m: round(v[m], 4) for m in METRICS} for k, v in results.items()},
                "indexer_chunks": len(indexer_chunks),
                "gold_intact": intact,
                "n": len(golden),
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
