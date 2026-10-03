"""Build the Azure AI Search index from the ingested corpus: chunk, embed, upload.

This is the one command that takes the corpus from files to a searchable index:

    uv run --all-groups python -m payments_rag.indexing

It validates and cleans the documents (``payments_rag.ingestion``), cuts them with every chunking
strategy, embeds each chunk with the Azure OpenAI embedding deployment, deletes and recreates the
index so no stale chunk survives, uploads everything, and records which corpus the index was built
from (``python -m payments_rag.ingestion --check-index`` reads that record).

It needs the deployed Azure resources (``infra/deploy.ps1``) and a signed-in ``az login``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .azure_clients import AzureOpenAIEmbedder, AzureSearchStore, AzureSettings
from .chunking import STRATEGIES, Chunk, chunk_document
from .ingestion import INDEX_MANIFEST, IngestedDocument, ingest, write_index_manifest

# About 80 words per chunk: short enough that a chunk holds one idea, long enough to carry
# context, and inside the 256-word-piece limit of the small local embedding model. The Azure
# model reads far more.
CHUNK_WORDS = 80
OVERLAP = 20
MAX_SENTENCES = 4


def chunk_corpus(documents: Sequence[IngestedDocument], strategy: str) -> list[Chunk]:
    """Cut every document with one strategy, attaching each document's title and source URL."""
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(
            chunk_document(
                document.text,
                doc_id=document.source.doc_id,
                strategy=strategy,
                title=document.source.title,
                source_url=document.source.url,
                jurisdiction=document.source.jurisdiction,
                source_type=document.source.source_type,
                published=document.source.published or "",
                chunk_size=CHUNK_WORDS,
                overlap=OVERLAP,
                max_sentences=MAX_SENTENCES,
            )
        )
    return chunks


def build_index(
    *,
    store: AzureSearchStore,
    embedder: Any,
    documents: Sequence[IngestedDocument] | None = None,
    strategies: Sequence[str] = STRATEGIES,
    manifest_path: Path = INDEX_MANIFEST,
) -> dict[str, int]:
    """Recreate the index from the corpus and return how many chunks each strategy uploaded."""
    documents = list(documents) if documents is not None else ingest()
    store.recreate_index()
    counts: dict[str, int] = {}
    for strategy in strategies:
        chunks = chunk_corpus(documents, strategy)
        store.upload(chunks, embedder([chunk.text for chunk in chunks]))
        counts[strategy] = len(chunks)
    write_index_manifest(documents, counts, path=manifest_path)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Azure AI Search index from the corpus.")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=list(STRATEGIES),
        choices=STRATEGIES,
        help="chunking strategies to upload (default: all four)",
    )
    args = parser.parse_args(argv)
    settings = AzureSettings.from_env()
    documents = ingest()
    print(f"ingested {len(documents)} documents; rebuilding index {settings.search_index!r} ...")
    counts = build_index(
        store=AzureSearchStore(settings),
        embedder=AzureOpenAIEmbedder(settings),
        documents=documents,
        strategies=args.strategies,
    )
    for strategy, count in counts.items():
        print(f"  {strategy:<16} {count} chunks")
    print("done. The index can take a few seconds to show new documents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
