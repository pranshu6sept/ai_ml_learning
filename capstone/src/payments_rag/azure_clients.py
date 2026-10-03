"""Azure clients for the capstone: Azure OpenAI (embeddings, chat) and Azure AI Search, keyless.

Authentication uses Microsoft Entra ID through ``DefaultAzureCredential`` (``az login`` locally),
so no API keys are stored. Needs the optional dependency group:  ``uv sync --group azure``.

STATUS: written against the SDKs' documented interfaces and unit-tested with fakes. It has not yet
been run against a live Azure service. ``capstone/evals/azure_smoke_test.py`` is the first test.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .chunking import Chunk
from .grounding import (
    NO_ANSWER,
    Answerability,
    CitedReply,
    GroundedAnswer,
    answerability_prompt,
    build_prompt,
    enforce_citations,
    parse_answerability,
)
from .retrieval import Hit

OPENAI_API_VERSION = "2024-10-21"  # documented GA Azure OpenAI data-plane version; override via env
OPENAI_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"
EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small
VECTOR_PROFILE = "payrag-hnsw-profile"
VECTOR_ALGORITHM = "payrag-hnsw"
_REQUIRED = {
    "AZURE_OPENAI_ENDPOINT": "openai_endpoint",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding_deployment",
    "AZURE_OPENAI_CHAT_DEPLOYMENT": "chat_deployment",
    "AZURE_SEARCH_ENDPOINT": "search_endpoint",
}


@dataclass(frozen=True)
class AzureSettings:
    """Where the deployed Azure resources are. Contains no secrets."""

    openai_endpoint: str
    embedding_deployment: str
    chat_deployment: str
    search_endpoint: str
    search_index: str = "payments-rag"
    openai_api_version: str = OPENAI_API_VERSION

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, dotenv: str | Path | None = ".env"
    ) -> AzureSettings:
        """Read settings from the environment, falling back to a ``.env`` file (see deploy.ps1)."""
        values: dict[str, str] = dict(read_dotenv(dotenv)) if dotenv else {}
        values.update(os.environ if env is None else env)
        missing = [name for name in _REQUIRED if not values.get(name)]
        if missing:
            raise ValueError(
                f"missing settings: {', '.join(missing)}. Run infra/deploy.ps1 (it writes .env) "
                "or copy .env.example to .env and fill it in."
            )
        return cls(
            **{field: values[name] for name, field in _REQUIRED.items()},
            search_index=values.get("AZURE_SEARCH_INDEX", "payments-rag"),
            openai_api_version=values.get("AZURE_OPENAI_API_VERSION", OPENAI_API_VERSION),
        )


def read_dotenv(path: str | Path | None) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines, ignoring blanks and ``#`` comments. No file gives ``{}``."""
    if path is None or not Path(path).is_file():
        return {}
    out: dict[str, str] = {}
    for line in (
        Path(path).read_text(encoding="utf-8-sig").splitlines()
    ):  # -sig: PowerShell adds a BOM
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip("\"'")
    return out


def _openai_client(settings: AzureSettings) -> Any:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    provider = get_bearer_token_provider(DefaultAzureCredential(), OPENAI_TOKEN_SCOPE)
    return AzureOpenAI(
        azure_endpoint=settings.openai_endpoint,
        azure_ad_token_provider=provider,
        api_version=settings.openai_api_version,
    )


class AzureOpenAIEmbedder:
    """Embeds text with an Azure OpenAI embedding deployment. Fits the ``Embedder`` protocol."""

    def __init__(
        self, settings: AzureSettings, *, client: Any | None = None, batch_size: int = 64
    ) -> None:
        self._deployment = settings.embedding_deployment
        self._client = client if client is not None else _openai_client(settings)
        self._batch_size = batch_size

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = self._client.embeddings.create(model=self._deployment, input=batch)
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        if not vectors:
            return np.zeros((0, EMBEDDING_DIMENSIONS), dtype=np.float32)
        array = np.asarray(vectors, dtype=np.float32)
        norms = np.maximum(np.linalg.norm(array, axis=1, keepdims=True), 1e-12)
        return np.asarray(array / norms, dtype=np.float32)


class AzureChatGenerator:
    """Writes the grounded answer. It never calls the model when the grounding rule abstained."""

    def __init__(
        self, settings: AzureSettings, *, client: Any | None = None, temperature: float = 0.0
    ) -> None:
        self._deployment = settings.chat_deployment
        self._client = client if client is not None else _openai_client(settings)
        self._temperature = temperature

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        """Send one user message and return the reply text. ``json_mode`` asks for a JSON object."""
        options: dict[str, Any] = {"response_format": {"type": "json_object"}} if json_mode else {}
        response = self._client.chat.completions.create(
            model=self._deployment,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
            **options,
        )
        return str(response.choices[0].message.content or "").strip()

    def generate(self, answer: GroundedAnswer) -> str:
        if answer.abstained:
            return NO_ANSWER  # no evidence, so no model call and no tokens spent
        return self.complete(build_prompt(answer))

    def check_answerability(self, question: str, evidence: Sequence[Hit]) -> Answerability:
        """Ask whether the passages state the answer, and verify the quote the model gives."""
        raw = self.complete(answerability_prompt(question, evidence), json_mode=True)
        return parse_answerability(raw, evidence)

    def generate_cited(self, answer: GroundedAnswer, *, retries: int = 1) -> CitedReply:
        """Strict prompt; if a sentence lacks a citation, ask once for a rewrite, then drop it.

        Dropping an uncited sentence can remove the sentence that actually answers the question
        (the model often leaves its lead sentence uncited), so each retry asks the model to rewrite
        with a citation on every sentence first. A retry is used only if it is strictly better: it
        must not become a refusal and must drop fewer sentences than the attempt before it (a tie
        can still lose the lead sentence and add rambling, as it did for q30).
        """
        if answer.abstained:
            return CitedReply(NO_ANSWER, (), 0, True)
        n = len(answer.evidence)
        prompt = build_prompt(answer, strict=True)
        result = enforce_citations(self.complete(prompt), n)
        for _ in range(retries):
            if not result.dropped or result.refused:
                break
            missing = "\n".join(f"- {sentence}" for sentence in result.dropped)
            reminder = (
                "\n\nYour previous answer had sentences without a citation:\n"
                f"{missing}\nWrite the whole answer again so that EVERY sentence ends with a "
                "citation such as [1], including the first sentence."
            )
            retry = enforce_citations(self.complete(prompt + reminder), n)
            if not retry.refused and len(retry.dropped) < len(result.dropped):
                result = retry
        return result


class AzureSearchStore:
    """One Azure AI Search index holding the chunks of every chunking strategy.

    The index has a text field and a vector field, so a query can run keyword and vector search
    together (Azure fuses the two rankings itself). Chunks are tagged with their strategy, so one
    index serves all four strategies (the free tier allows only three indexes).
    """

    _SELECT = ["id", "text", "doc_id", "section", "source_url", "title", "strategy", "chunk_index"]

    def __init__(
        self,
        settings: AzureSettings,
        *,
        index_client: Any | None = None,
        search_client: Any | None = None,
    ) -> None:
        self._settings = settings
        if index_client is None or search_client is None:
            from azure.identity import DefaultAzureCredential
            from azure.search.documents import SearchClient
            from azure.search.documents.indexes import SearchIndexClient

            credential = DefaultAzureCredential()
            index_client = index_client or SearchIndexClient(settings.search_endpoint, credential)
            search_client = search_client or SearchClient(
                settings.search_endpoint, settings.search_index, credential
            )
        self._index_client = index_client
        self._search_client = search_client

    def recreate_index(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        """Delete the index (if it exists) and create it empty, so no stale chunks survive.

        Uploading is an upsert: chunks whose text changed or that no longer exist would otherwise
        stay in the index. Use this before re-uploading a corpus that has changed.
        """
        from azure.core.exceptions import ResourceNotFoundError

        with contextlib.suppress(ResourceNotFoundError):  # nothing to delete on a first run
            self._index_client.delete_index(self._settings.search_index)
        self.ensure_index(dimensions)

    def ensure_index(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        """Create the index, or update it if it exists (safe to repeat)."""
        from azure.search.documents.indexes.models import (
            HnswAlgorithmConfiguration,
            SearchableField,
            SearchField,
            SearchFieldDataType,
            SearchIndex,
            SimpleField,
            VectorSearch,
            VectorSearchProfile,
        )

        kinds: Any = SearchFieldDataType  # the SDK's enum types confuse static type checkers
        text = kinds.String
        fields = [
            SimpleField(name="id", type=text, key=True, filterable=True),
            SearchableField(name="text", type=text),
            SimpleField(name="doc_id", type=text, filterable=True, facetable=True),
            SearchableField(name="section", type=text),
            SimpleField(name="source_url", type=text),
            SimpleField(name="title", type=text),
            SimpleField(name="strategy", type=text, filterable=True, facetable=True),
            SimpleField(name="chunk_index", type=kinds.Int32, filterable=True),
            SearchField(
                name="vector",
                type=kinds.Collection(kinds.Single),
                searchable=True,
                vector_search_dimensions=dimensions,
                vector_search_profile_name=VECTOR_PROFILE,
            ),
        ]
        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name=VECTOR_ALGORITHM)],
            profiles=[
                VectorSearchProfile(
                    name=VECTOR_PROFILE, algorithm_configuration_name=VECTOR_ALGORITHM
                )
            ],
        )
        index = SearchIndex(
            name=self._settings.search_index, fields=fields, vector_search=vector_search
        )
        self._index_client.create_or_update_index(index)

    def upload(self, chunks: Sequence[Chunk], vectors: np.ndarray, batch_size: int = 500) -> int:
        """Upload chunks with their vectors; returns how many documents were sent."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        documents = [
            {
                "id": f"{chunk.strategy}-{chunk.doc_id}-{chunk.chunk_index}",
                "text": chunk.text,
                "doc_id": chunk.doc_id,
                "section": chunk.section,
                "source_url": chunk.source_url,
                "title": chunk.title,
                "strategy": chunk.strategy,
                "chunk_index": chunk.chunk_index,
                "vector": [float(x) for x in vector],
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        for start in range(0, len(documents), batch_size):
            self._search_client.upload_documents(documents=documents[start : start + batch_size])
        return len(documents)

    def search(
        self, query: str, vector: Sequence[float], top_k: int = 3, strategy: str | None = None
    ) -> list[Hit]:
        """Hybrid search (keyword plus vector), optionally limited to one chunking strategy."""
        from azure.search.documents.models import VectorizedQuery

        vector_query = VectorizedQuery(
            vector=[float(x) for x in vector], k_nearest_neighbors=max(top_k, 50), fields="vector"
        )
        results = self._search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=f"strategy eq '{strategy}'" if strategy else None,
            select=self._SELECT,
            top=top_k,
        )
        hits = []
        for row in results:
            chunk = Chunk(
                text=row["text"],
                chunk_index=int(row["chunk_index"]),
                doc_id=row["doc_id"],
                section=row.get("section") or "",
                source_url=row.get("source_url") or "",
                strategy=row.get("strategy") or "",
                title=row.get("title") or "",
            )
            hits.append(Hit(chunk, float(row["@search.score"])))
        return hits


class AzureHybridRetriever:
    """Adapts the Azure index to the ``search(query, top_k)`` shape of the local ``Retriever``."""

    def __init__(
        self, store: AzureSearchStore, embedder: AzureOpenAIEmbedder, strategy: str | None = None
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._strategy = strategy

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        vector = self._embedder([query])[0]
        return self._store.search(query, vector, top_k=top_k, strategy=self._strategy)
