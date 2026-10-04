# ruff: noqa: E501
"""The managed alternative to ``indexing.py``: Blob Storage -> Azure AI Search indexer -> skillset.

``indexing.py`` (push) chunks and embeds in our own code and uploads the chunks. Here Azure does it:

    cleaned documents in Blob Storage
      -> blob indexer (reads the blobs with the search service's managed identity)
      -> skillset: Text Split (cut into pages) + Azure OpenAI embedding (one vector per page)
      -> index projections (each page becomes its own search document, linked to its parent)

No keys anywhere: the indexer reads Blob Storage as the search service's identity and calls Azure OpenAI
as the same identity (role assignments are in ``infra/week7.bicep``). Needs a search service on the Basic
tier or higher, because the free tier cannot use a managed identity for indexers.

What this path cannot do that ours can: keep the heading path (``section``) and cut on document structure.
Text Split cuts by length (with overlap, on sentence boundaries when it can).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

PAGE_CHARS = 600  # about the size of one of our 80-word chunks
PAGE_OVERLAP = 100


@dataclass(frozen=True)
class IndexerNames:
    data_source: str = "corpus-blobs"
    index: str = "payments-blob-index"
    skillset: str = "corpus-skills"
    indexer: str = "corpus-indexer"


def upload_corpus(account: str, container: str, documents: dict[str, str], credential: Any) -> int:
    """Upload one blob per document (named ``<doc_id>.md``), replacing any older copy."""
    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=credential)
    client = service.get_container_client(container)
    for doc_id, text in documents.items():
        client.upload_blob(f"{doc_id}.md", text.encode("utf-8"), overwrite=True)
    return len(documents)


def build_pipeline(
    index_client: Any,
    indexer_client: Any,
    *,
    names: IndexerNames,
    storage_resource_id: str,
    container: str,
    openai_endpoint: str,
    embedding_deployment: str,
    dimensions: int,
) -> None:
    """Create (or update) the data source, index, skillset and indexer. Safe to repeat."""
    from azure.search.documents.indexes.models import (
        AzureOpenAIEmbeddingSkill,
        HnswAlgorithmConfiguration,
        IndexProjectionMode,
        InputFieldMappingEntry,
        OutputFieldMappingEntry,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SearchIndexer,
        SearchIndexerDataContainer,
        SearchIndexerDataSourceConnection,
        SearchIndexerIndexProjection,
        SearchIndexerIndexProjectionSelector,
        SearchIndexerIndexProjectionsParameters,
        SearchIndexerSkillset,
        SimpleField,
        SplitSkill,
        VectorSearch,
        VectorSearchProfile,
    )

    kinds: Any = SearchFieldDataType
    text = kinds.String
    index_client.create_or_update_index(
        SearchIndex(
            name=names.index,
            fields=[
                SearchField(
                    name="id",
                    type=text,
                    key=True,
                    searchable=True,
                    filterable=True,
                    sortable=True,
                    analyzer_name="keyword",
                ),
                SimpleField(name="parent_id", type=text, filterable=True),
                SearchableField(name="text", type=text),
                SimpleField(name="doc_id", type=text, filterable=True),
                SearchField(
                    name="vector",
                    type=kinds.Collection(kinds.Single),
                    searchable=True,
                    vector_search_dimensions=dimensions,
                    vector_search_profile_name="blob-profile",
                ),
            ],
            vector_search=VectorSearch(
                algorithms=[HnswAlgorithmConfiguration(name="blob-hnsw")],
                profiles=[
                    VectorSearchProfile(
                        name="blob-profile", algorithm_configuration_name="blob-hnsw"
                    )
                ],
            ),
        )
    )
    # The data source reads the container as the search service's managed identity (no account key).
    indexer_client.create_or_update_data_source_connection(
        SearchIndexerDataSourceConnection(
            name=names.data_source,
            type="azureblob",
            connection_string=f"ResourceId={storage_resource_id};",
            container=SearchIndexerDataContainer(name=container),
        )
    )
    split = SplitSkill(
        name="split",
        context="/document",
        text_split_mode="pages",
        maximum_page_length=PAGE_CHARS,
        page_overlap_length=PAGE_OVERLAP,
        inputs=[InputFieldMappingEntry(name="text", source="/document/content")],
        outputs=[OutputFieldMappingEntry(name="textItems", target_name="pages")],
    )
    embed = AzureOpenAIEmbeddingSkill(
        name="embed",
        context="/document/pages/*",
        resource_url=openai_endpoint.rstrip("/"),
        deployment_name=embedding_deployment,
        model_name="text-embedding-3-small",
        dimensions=dimensions,
        inputs=[InputFieldMappingEntry(name="text", source="/document/pages/*")],
        outputs=[OutputFieldMappingEntry(name="embedding", target_name="vector")],
    )
    projection = SearchIndexerIndexProjection(
        selectors=[
            SearchIndexerIndexProjectionSelector(
                target_index_name=names.index,
                parent_key_field_name="parent_id",
                source_context="/document/pages/*",
                mappings=[
                    InputFieldMappingEntry(name="text", source="/document/pages/*"),
                    InputFieldMappingEntry(name="vector", source="/document/pages/*/vector"),
                    InputFieldMappingEntry(name="doc_id", source="/document/metadata_storage_name"),
                ],
            )
        ],
        parameters=SearchIndexerIndexProjectionsParameters(
            projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
        ),
    )
    indexer_client.create_or_update_skillset(
        SearchIndexerSkillset(
            name=names.skillset,
            description="Split blobs into pages and embed each page",
            skills=[split, embed],
            index_projection=projection,
        )
    )
    indexer_client.create_or_update_indexer(
        SearchIndexer(
            name=names.indexer,
            data_source_name=names.data_source,
            target_index_name=names.index,
            skillset_name=names.skillset,
        )
    )


def run_and_wait(
    indexer_client: Any, name: str, *, timeout_s: int = 900, poll_s: int = 5
) -> dict[str, Any]:
    """Reset and run the indexer, wait for it to finish, and return what happened."""
    # A newly created indexer starts its first run by itself; let it finish before resetting.
    # (The service-level status "running" only means the indexer is enabled; the run state is in
    # last_result.status.)
    while True:
        last = indexer_client.get_indexer_status(name).last_result
        if last is not None and last.status != "inProgress":
            break
        time.sleep(poll_s)
    indexer_client.reset_indexer(name)
    started = time.monotonic()
    indexer_client.run_indexer(name)
    while time.monotonic() - started < timeout_s:
        time.sleep(poll_s)
        status = indexer_client.get_indexer_status(name)
        last = status.last_result
        if last is not None and last.status in ("success", "transientFailure", "persistentFailure"):
            return {
                "status": last.status,
                "seconds": round(time.monotonic() - started, 1),
                "items_processed": last.item_count,
                "items_failed": last.failed_item_count,
                "errors": [f"{e.key}: {e.error_message}" for e in (last.errors or [])][:5],
                "warnings": [f"{w.key}: {w.message}" for w in (last.warnings or [])][:5],
            }
    raise TimeoutError(f"indexer {name!r} did not finish within {timeout_s} s")


def documents_from(sources: Sequence[Any]) -> dict[str, str]:
    """``{doc_id: cleaned text}`` from ``ingestion.ingest()`` results."""
    return {d.source.doc_id: d.text for d in sources}
