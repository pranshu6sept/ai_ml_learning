# ruff: noqa: E501
"""Build the Blob Storage -> indexer -> skillset pipeline on the Week 7 Basic search service and run it.

    uv run --all-groups python capstone/evals/run_blob_indexer.py

Reads AZURE_W7_SEARCH_ENDPOINT, AZURE_W7_STORAGE_ACCOUNT and AZURE_W7_STORAGE_RESOURCE_ID from `.env`
(written after `infra/week7.bicep` is deployed with the indexer search service switched on), plus the
usual Azure OpenAI settings. Needs `az login`. Writes `results/blob_indexer_run.json`.
"""

from __future__ import annotations

import json
import sys

from evaluate_chunking import HERE
from run_retrieval import RESULTS

from payments_rag import AzureSettings
from payments_rag.azure_clients import EMBEDDING_DIMENSIONS, read_dotenv
from payments_rag.blob_indexing import (
    IndexerNames,
    build_pipeline,
    documents_from,
    run_and_wait,
    upload_corpus,
)
from payments_rag.ingestion import ingest

ENV = HERE.parents[1] / ".env"


def main() -> None:
    from azure.identity import DefaultAzureCredential
    from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    values = read_dotenv(ENV)
    endpoint = values["AZURE_W7_SEARCH_ENDPOINT"]
    account = values["AZURE_W7_STORAGE_ACCOUNT"]
    settings = AzureSettings.from_env()
    credential = DefaultAzureCredential()
    names = IndexerNames()

    documents = documents_from(ingest())
    print(f"uploading {len(documents)} cleaned documents to {account}/corpus ...")
    upload_corpus(account, "corpus", documents, credential)

    print("creating data source, index, skillset and indexer ...")
    build_pipeline(
        SearchIndexClient(endpoint, credential),
        SearchIndexerClient(endpoint, credential),
        names=names,
        storage_resource_id=values["AZURE_W7_STORAGE_RESOURCE_ID"],
        container="corpus",
        openai_endpoint=settings.openai_endpoint,
        embedding_deployment=settings.embedding_deployment,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    print("running the indexer ...")
    result = run_and_wait(SearchIndexerClient(endpoint, credential), names.indexer)
    print(json.dumps(result, indent=2))
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "blob_indexer_run.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
