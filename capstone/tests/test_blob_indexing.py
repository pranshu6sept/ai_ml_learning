from types import SimpleNamespace
from typing import Any

import pytest

from payments_rag.blob_indexing import IndexerNames, build_pipeline, run_and_wait


class FakeIndexClient:
    def __init__(self) -> None:
        self.index: Any = None

    def create_or_update_index(self, index: Any) -> None:
        self.index = index


class FakeIndexerClient:
    """Records what is created, and replays scripted run states."""

    def __init__(self, states: list[Any] | None = None) -> None:
        self.created: dict[str, Any] = {}
        self.calls: list[str] = []
        self.states = list(states or [])

    def create_or_update_data_source_connection(self, obj: Any) -> None:
        self.created["data_source"] = obj

    def create_or_update_skillset(self, obj: Any) -> None:
        self.created["skillset"] = obj

    def create_or_update_indexer(self, obj: Any) -> None:
        self.created["indexer"] = obj

    def reset_indexer(self, name: str) -> None:
        self.calls.append("reset")

    def run_indexer(self, name: str) -> None:
        self.calls.append("run")

    def get_indexer_status(self, name: str) -> Any:
        self.calls.append("status")
        last = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return SimpleNamespace(
            status="running", last_result=last
        )  # "running" = the indexer is enabled


def _run(status: str, start: int = 1, **extra: Any) -> Any:
    base = {"item_count": 11, "failed_item_count": 0, "errors": [], "warnings": []}
    return SimpleNamespace(status=status, start_time=start, **{**base, **extra})


def _build() -> tuple[FakeIndexClient, FakeIndexerClient]:
    pytest.importorskip("azure.search.documents")
    index, indexer = FakeIndexClient(), FakeIndexerClient()
    build_pipeline(
        index,
        indexer,
        names=IndexerNames(),
        storage_resource_id="/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/acct",
        container="corpus",
        openai_endpoint="https://oai.example.com/",
        embedding_deployment="emb",
        dimensions=1536,
    )
    return index, indexer


def test_the_data_source_reads_blobs_with_a_managed_identity_and_no_key() -> None:
    _, indexer = _build()

    connection = indexer.created["data_source"].credentials.connection_string

    assert connection.startswith("ResourceId=/subscriptions/")
    assert "AccountKey" not in connection and "SharedAccessSignature" not in connection
    assert indexer.created["data_source"].container.name == "corpus"


def test_the_skillset_splits_into_pages_then_embeds_each_page() -> None:
    _, indexer = _build()

    split, embed = indexer.created["skillset"].skills

    assert split.maximum_page_length == 600 and split.page_overlap_length == 100
    assert embed.deployment_name == "emb" and embed.dimensions == 1536
    assert embed.resource_url == "https://oai.example.com"  # no trailing slash
    assert embed.context == "/document/pages/*"


def test_each_page_becomes_its_own_search_document_and_the_parent_is_not_indexed() -> None:
    _, indexer = _build()

    projection = indexer.created["skillset"].index_projection

    selector = projection.selectors[0]
    assert (
        selector.source_context == "/document/pages/*"
        and selector.parent_key_field_name == "parent_id"
    )
    assert {m.name for m in selector.mappings} == {"text", "vector", "doc_id"}
    assert str(projection.parameters.projection_mode).endswith(
        "SKIP_INDEXING_PARENT_DOCUMENTS"
    ) or (projection.parameters.projection_mode == "skipIndexingParentDocuments")


def test_the_index_has_a_vector_field_of_the_embedding_size() -> None:
    index, _ = _build()

    fields = {f.name: f for f in index.index.fields}

    assert fields["vector"].as_dict()["dimensions"] == 1536
    assert {"id", "parent_id", "text", "doc_id"} <= fields.keys()


def test_running_waits_for_the_automatic_first_run_then_resets_and_reruns() -> None:
    client = FakeIndexerClient(
        [_run("inProgress"), _run("success"), _run("success"), _run("success", start=2)]
    )

    result = run_and_wait(client, "corpus-indexer", poll_s=0)

    assert client.calls.index("reset") > client.calls.index("status")  # waited before resetting
    assert client.calls.index("run") > client.calls.index("reset")
    assert result["status"] == "success" and result["items_processed"] == 11


def test_a_failed_run_is_reported_with_its_errors_not_hidden() -> None:
    failing = _run(
        "transientFailure",
        start=2,
        failed_item_count=1,
        errors=[SimpleNamespace(key="doc1", error_message="429 from the embedding model")],
    )
    client = FakeIndexerClient([_run("success"), _run("success"), failing])

    result = run_and_wait(client, "corpus-indexer", poll_s=0)

    assert result["status"] == "transientFailure" and result["items_failed"] == 1
    assert "429" in result["errors"][0]


def test_a_run_that_never_finishes_times_out() -> None:
    client = FakeIndexerClient([_run("success"), _run("success"), _run("inProgress", start=2)])

    with pytest.raises(TimeoutError):
        run_and_wait(client, "corpus-indexer", timeout_s=0, poll_s=0)

    # After the call the old result is still on show; only a run with a new start time counts.
    states = [
        _run("success"),
        _run("success"),
        _run("success"),
        _run("success", start=2, item_count=1),
    ]
    client = FakeIndexerClient(states)

    result = run_and_wait(client, "corpus-indexer", poll_s=0, reset=False)

    assert "reset" not in client.calls
    assert result["items_processed"] == 1  # not the stale 11 from the previous run


def test_a_deletion_policy_and_a_schedule_are_optional_extras_on_the_pipeline() -> None:
    pytest.importorskip("azure.search.documents")
    index, indexer = FakeIndexClient(), FakeIndexerClient()
    build_pipeline(
        index,
        indexer,
        names=IndexerNames(),
        storage_resource_id="/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/a",
        container="corpus",
        openai_endpoint="https://oai.example.com/",
        embedding_deployment="emb",
        dimensions=1536,
        soft_delete=True,
        schedule_minutes=5,
    )

    assert indexer.created["data_source"].data_deletion_detection_policy is not None
    assert indexer.created["indexer"].schedule.interval.total_seconds() == 300
    plain = _build()[1]
    assert plain.created["data_source"].data_deletion_detection_policy is None
    assert plain.created["indexer"].schedule is None


def test_a_user_assigned_identity_is_used_for_both_blob_access_and_the_embedding_skill() -> None:
    pytest.importorskip("azure.search.documents")
    index, indexer = FakeIndexClient(), FakeIndexerClient()
    identity_id = (
        "/subscriptions/s/resourceGroups/rg/providers/Microsoft.ManagedIdentity/"
        "userAssignedIdentities/i"
    )
    build_pipeline(
        index,
        indexer,
        names=IndexerNames(),
        storage_resource_id="/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/a",
        container="corpus",
        openai_endpoint="https://oai.example.com/",
        embedding_deployment="emb",
        dimensions=1536,
        identity_resource_id=identity_id,
    )

    source = indexer.created["data_source"].identity.as_dict()
    embed = indexer.created["skillset"].skills[1].auth_identity.as_dict()
    assert source["userAssignedIdentity"] == identity_id
    assert embed["userAssignedIdentity"] == identity_id
    assert (
        _build()[1].created["data_source"].identity is None
    )  # default: the service's own identity
