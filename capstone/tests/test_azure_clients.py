"""Unit tests for the Azure clients using fakes; no Azure account or network is needed."""

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from payments_rag import (
    NO_ANSWER,
    AzureChatGenerator,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    Chunk,
    GroundedAnswer,
    Hit,
)
from payments_rag.azure_clients import read_dotenv

ENV = {
    "AZURE_OPENAI_ENDPOINT": "https://oai.example.com/",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "text-embedding-3-small",
    "AZURE_OPENAI_CHAT_DEPLOYMENT": "gpt-4.1-mini",
    "AZURE_SEARCH_ENDPOINT": "https://search.example.com",
}
SETTINGS = AzureSettings.from_env(ENV, dotenv=None)


def test_settings_report_every_missing_variable() -> None:
    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT.*AZURE_SEARCH_ENDPOINT"):
        AzureSettings.from_env({"AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "x"}, dotenv=None)


def test_settings_read_a_dotenv_file_and_the_environment_wins(tmp_path: Any) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# comment\nAZURE_OPENAI_ENDPOINT=https://from-file\n"
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT='emb'\nAZURE_OPENAI_CHAT_DEPLOYMENT=chat\n"
        "AZURE_SEARCH_ENDPOINT=https://search\n",
        encoding="utf-8",
    )

    settings = AzureSettings.from_env({"AZURE_OPENAI_ENDPOINT": "https://from-env"}, dotenv)

    assert settings.openai_endpoint == "https://from-env"
    assert settings.embedding_deployment == "emb"
    assert settings.search_index == "payments-rag"


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def create(self, model: str, input: list[str]) -> Any:  # noqa: A002 - mirrors the SDK
        self.calls.append(input)
        # Return rows out of order to prove the embedder sorts by index.
        data = [
            SimpleNamespace(index=i, embedding=[float(i + 1), 0.0, 0.0]) for i in range(len(input))
        ]
        return SimpleNamespace(data=list(reversed(data)))


def test_embedder_batches_keeps_order_and_normalises() -> None:
    fake = FakeEmbeddings()
    embedder = AzureOpenAIEmbedder(SETTINGS, client=SimpleNamespace(embeddings=fake), batch_size=2)

    vectors = embedder(["a", "b", "c", "d", "e"])

    assert [len(call) for call in fake.calls] == [2, 2, 1]
    assert vectors.shape == (5, 3)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert embedder([]).shape[0] == 0


class FakeChat:
    def __init__(self) -> None:
        self.messages: list[Any] = []
        self.completions = self

    def create(self, **kwargs: Any) -> Any:
        self.messages.append(kwargs)
        message = SimpleNamespace(content="  Answer [1].  ")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_generator_does_not_call_the_model_when_the_rule_abstained() -> None:
    chat = FakeChat()
    generator = AzureChatGenerator(SETTINGS, client=SimpleNamespace(chat=chat))

    answer = GroundedAnswer("Q?", True, (), "nothing matched")

    assert generator.generate(answer) == NO_ANSWER
    assert chat.messages == []


def test_generator_sends_the_grounded_prompt_and_returns_the_reply() -> None:
    chat = FakeChat()
    generator = AzureChatGenerator(SETTINGS, client=SimpleNamespace(chat=chat))
    evidence = (Hit(Chunk("PSD2 bans retailer surcharges.", 0, "psd2"), 3.0),)

    reply = generator.generate(GroundedAnswer("Can shops add surcharges?", False, evidence, "ok"))

    assert reply == "Answer [1]."
    sent = chat.messages[0]
    assert sent["model"] == "gpt-4.1-mini"
    assert "[1] PSD2 bans retailer surcharges." in sent["messages"][0]["content"]


class FakeSearchClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.uploaded: list[list[dict[str, Any]]] = []
        self.search_kwargs: dict[str, Any] = {}
        self.rows = rows or []

    def upload_documents(self, documents: list[dict[str, Any]]) -> None:
        self.uploaded.append(documents)

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.search_kwargs = kwargs
        return self.rows


class FakeIndexClient:
    def __init__(self) -> None:
        self.index: Any = None

    def create_or_update_index(self, index: Any) -> None:
        self.index = index


def _store(rows: list[dict[str, Any]] | None = None) -> tuple[AzureSearchStore, Any, Any]:
    search, index = FakeSearchClient(rows), FakeIndexClient()
    return AzureSearchStore(SETTINGS, index_client=index, search_client=search), search, index


def test_upload_builds_one_document_per_chunk_with_a_unique_id() -> None:
    store, search, _ = _store()
    chunks = [
        Chunk("alpha", 0, "doc", "Sec", "https://u", "fixed", "Title"),
        Chunk("beta", 1, "doc", "Sec", "https://u", "fixed", "Title"),
        Chunk("alpha", 0, "doc", "Sec", "https://u", "recursive", "Title"),
    ]

    sent = store.upload(chunks, np.eye(3, dtype=np.float32), batch_size=2)

    docs = [d for batch in search.uploaded for d in batch]
    assert sent == 3 and len(search.uploaded) == 2
    assert len({d["id"] for d in docs}) == 3  # same text in two strategies must not collide
    assert docs[0]["vector"] == [1.0, 0.0, 0.0]
    assert docs[0]["strategy"] == "fixed"
    with pytest.raises(ValueError, match="same length"):
        store.upload(chunks, np.eye(2, dtype=np.float32))


def test_ensure_index_declares_a_text_field_and_a_vector_field() -> None:
    pytest.importorskip("azure.search.documents")
    store, _, index_client = _store()

    store.ensure_index(dimensions=3)

    fields = {f.name: f for f in index_client.index.fields}
    assert index_client.index.name == "payments-rag"
    assert {"id", "text", "doc_id", "section", "strategy", "vector"} <= fields.keys()
    assert fields["vector"].as_dict()["dimensions"] == 3
    assert fields["strategy"].filterable


def test_search_sends_text_and_vector_and_filters_by_strategy() -> None:
    pytest.importorskip("azure.search.documents")
    rows = [
        {
            "text": "PSD2 bans retailer surcharges.",
            "chunk_index": 2,
            "doc_id": "psd2_overview",
            "section": "PSD2 > Fees",
            "source_url": "https://eu",
            "strategy": "structure_aware",
            "title": "PSD2",
            "@search.score": 0.0327,
        }
    ]
    store, search, _ = _store(rows)

    hits = store.search("surcharges?", [0.1, 0.2], top_k=3, strategy="structure_aware")

    assert search.search_kwargs["search_text"] == "surcharges?"
    assert search.search_kwargs["filter"] == "strategy eq 'structure_aware'"
    assert search.search_kwargs["top"] == 3
    assert len(search.search_kwargs["vector_queries"]) == 1
    assert hits[0].chunk.doc_id == "psd2_overview" and hits[0].score == pytest.approx(0.0327)


def test_hybrid_retriever_embeds_the_query_then_searches() -> None:
    pytest.importorskip("azure.search.documents")
    store, search, _ = _store([])
    embedder = AzureOpenAIEmbedder(
        SETTINGS, client=SimpleNamespace(embeddings=FakeEmbeddings()), batch_size=8
    )

    result = AzureHybridRetriever(store, embedder, "fixed").search("a question", top_k=5)

    assert result == []
    assert search.search_kwargs["search_text"] == "a question"
    assert search.search_kwargs["filter"] == "strategy eq 'fixed'"


def test_dotenv_with_a_byte_order_mark_is_read_correctly(tmp_path: Any) -> None:
    # Windows PowerShell 5.1 writes UTF-8 files with a BOM; the first key must not be corrupted.
    dotenv = tmp_path / ".env"
    bom = bytes([0xEF, 0xBB, 0xBF])
    dotenv.write_bytes(bom + b"AZURE_OPENAI_ENDPOINT=https://oai\nAZURE_SEARCH_INDEX=idx\n")

    assert read_dotenv(dotenv) == {
        "AZURE_OPENAI_ENDPOINT": "https://oai",
        "AZURE_SEARCH_INDEX": "idx",
    }


def test_complete_requests_json_only_when_asked() -> None:
    chat = FakeChat()
    generator = AzureChatGenerator(SETTINGS, client=SimpleNamespace(chat=chat))

    generator.complete("plain")
    generator.complete("as json", json_mode=True)

    assert "response_format" not in chat.messages[0]
    assert chat.messages[1]["response_format"] == {"type": "json_object"}
    assert chat.messages[1]["messages"][0]["content"] == "as json"


class RecordingIndexClient(FakeIndexClient):
    def __init__(self, *, missing: bool = False) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.missing = missing

    def delete_index(self, name: str) -> None:
        from azure.core.exceptions import ResourceNotFoundError

        self.calls.append(f"delete {name}")
        if self.missing:
            raise ResourceNotFoundError("no such index")

    def create_or_update_index(self, index: Any) -> None:
        self.calls.append("create")
        super().create_or_update_index(index)


def test_recreate_deletes_the_old_index_before_creating_the_new_one() -> None:
    pytest.importorskip("azure.search.documents")
    index = RecordingIndexClient()
    store = AzureSearchStore(SETTINGS, index_client=index, search_client=FakeSearchClient())

    store.recreate_index()

    assert index.calls == ["delete payments-rag", "create"]


def test_recreate_works_on_a_first_run_when_there_is_no_index_to_delete() -> None:
    pytest.importorskip("azure.search.documents")
    index = RecordingIndexClient(missing=True)
    store = AzureSearchStore(SETTINGS, index_client=index, search_client=FakeSearchClient())

    store.recreate_index()

    assert index.calls == ["delete payments-rag", "create"]
    assert index.index is not None


def _row(**extra: Any) -> dict[str, Any]:
    return {
        "text": "PSD2 bans retailer surcharges.",
        "chunk_index": 2,
        "doc_id": "psd2_overview",
        "section": "PSD2 > Fees",
        "source_url": "https://eu",
        "strategy": "structure_aware",
        "title": "PSD2",
        "@search.score": 0.0327,
        **extra,
    }


def test_the_index_declares_a_semantic_configuration_for_the_section_and_text() -> None:
    pytest.importorskip("azure.search.documents")
    store, _, index_client = _store()

    store.ensure_index(dimensions=3)

    semantic = index_client.index.semantic_search.as_dict()
    assert semantic["defaultConfiguration"] == "payrag-semantic"
    prioritized = semantic["configurations"][0]["prioritizedFields"]
    assert prioritized["titleField"] == {"fieldName": "section"}
    assert prioritized["prioritizedContentFields"] == [{"fieldName": "text"}]


def test_semantic_search_asks_for_the_ranker_fails_loudly_and_uses_its_score() -> None:
    pytest.importorskip("azure.search.documents")
    store, search, _ = _store([_row(**{"@search.reranker_score": 2.75})])

    hits = store.search("surcharges?", [0.1, 0.2], top_k=3, semantic=True)

    assert search.search_kwargs["query_type"] == "semantic"
    assert search.search_kwargs["semantic_configuration_name"] == "payrag-semantic"
    assert search.search_kwargs["semantic_error_mode"] == "fail"  # never fall back silently
    assert hits[0].score == pytest.approx(2.75)  # the ranker's score, not the fused 0.0327


def test_ordinary_search_sends_no_semantic_options() -> None:
    pytest.importorskip("azure.search.documents")
    store, search, _ = _store([_row()])

    hits = store.search("surcharges?", [0.1, 0.2], top_k=3)

    assert (
        not {"query_type", "semantic_configuration_name", "semantic_error_mode"}
        & search.search_kwargs.keys()
    )
    assert hits[0].score == pytest.approx(0.0327)


def test_the_retriever_passes_the_semantic_flag_through() -> None:
    pytest.importorskip("azure.search.documents")
    store, search, _ = _store([_row(**{"@search.reranker_score": 3.1})])

    class Embedder:
        def __call__(self, texts: Any) -> Any:
            return [[0.1, 0.2] for _ in texts]

    retriever = AzureHybridRetriever(store, Embedder(), "structure_aware", semantic=True)  # type: ignore[arg-type]

    assert retriever.search("surcharges?", top_k=1)[0].score == pytest.approx(3.1)
    assert search.search_kwargs["query_type"] == "semantic"
