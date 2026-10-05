# ruff: noqa: E501
"""text-embedding-3-large (3072 dimensions) vs text-embedding-3-small (1536) on the golden set.

Builds a second index, `payments-rag-large`, on the same search service with the large model (the
"small" index is the one Week 4 built), then scores the same Azure hybrid search (keyword + vector, no
semantic ranker) over the same chunks. Only the embedding model differs.

    uv run --all-groups python capstone/evals/run_embedding_large.py [--skip-build]

Needs `az login` and a `text-embedding-3-large` deployment (infra/main.bicep). The index and manifest
for the large index do not touch the committed Week 4 index manifest. Writes `results/embedding_large.md|json`.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from evaluate_chunking import META_SECTIONS, evaluate, load_documents
from run_retrieval import METRICS, RESULTS, load_golden

from payments_rag import (
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    strip_sections,
)
from payments_rag.indexing import build_index
from payments_rag.ingestion import ingest

LARGE_DEPLOYMENT = "text-embedding-3-large"
LARGE_INDEX = "payments-rag-large"
LARGE_DIMENSIONS = 3072
STRATEGIES = ("fixed", "structure_aware")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--skip-build", action="store_true", help="reuse the large index if it exists"
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    small = AzureSettings.from_env()
    large = dataclasses.replace(
        small, search_index=LARGE_INDEX, embedding_deployment=LARGE_DEPLOYMENT
    )
    large_store, large_embedder = AzureSearchStore(large), AzureOpenAIEmbedder(large)

    if not args.skip_build:
        print(f"building {LARGE_INDEX} ({LARGE_DIMENSIONS} dimensions) ...", flush=True)
        counts = build_index(
            store=large_store,
            embedder=large_embedder,
            documents=ingest(),
            strategies=STRATEGIES,
            manifest_path=RESULTS / "embedding_large_index_manifest.json",
            dimensions=LARGE_DIMENSIONS,
        )
        print(counts, flush=True)

    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = [q for q in load_golden(documents) if q["expected"] == "answer"]
    small_store, small_embedder = AzureSearchStore(small), AzureOpenAIEmbedder(small)

    results: dict[str, dict[str, dict]] = {}
    for strategy in STRATEGIES:
        results[strategy] = {
            "small (1536)": evaluate(
                strategy,
                documents,
                golden,
                retriever_factory=lambda _c, s=strategy: AzureHybridRetriever(
                    small_store, small_embedder, s
                ),
            ),
            "large (3072)": evaluate(
                strategy,
                documents,
                golden,
                retriever_factory=lambda _c, s=strategy: AzureHybridRetriever(
                    large_store, large_embedder, s
                ),
            ),
        }
        print(f"scored {strategy}", flush=True)

    lines = [
        f"{len(golden)} answerable golden questions; Azure hybrid search (keyword + vector, no semantic ranker); same chunks, only the embedding model differs. One question is worth {1 / len(golden):.3f}.\n",
        "| Chunking | Embedding | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for strategy, by_model in results.items():
        for model, r in by_model.items():
            lines.append(
                f"| {strategy} | {model} | " + " | ".join(f"{r[m]:.2f}" for m in METRICS) + " |"
            )
    text = "\n".join(lines) + "\n"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "embedding_large.md").write_text(text, encoding="utf-8")
    (RESULTS / "embedding_large.json").write_text(
        json.dumps(
            {
                s: {m: {k: round(v[k], 4) for k in METRICS} for m, v in d.items()}
                for s, d in results.items()
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
