import json
from pathlib import Path
from typing import Any

import numpy as np

from payments_rag import STRATEGIES, chunk_document
from payments_rag.indexing import CHUNK_WORDS, MAX_SENTENCES, OVERLAP, build_index, chunk_corpus
from payments_rag.ingestion import corpus_sha256, ingest


class FakeStore:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.uploads: dict[str, list[Any]] = {}

    def recreate_index(self) -> None:
        self.events.append("recreate")

    def upload(self, chunks: Any, vectors: Any) -> int:
        assert len(chunks) == len(vectors)
        self.events.append(f"upload {chunks[0].strategy}")
        self.uploads[chunks[0].strategy] = list(chunks)
        return len(chunks)


def _embed(texts: list[str]) -> np.ndarray:
    return np.zeros((len(texts), 3), dtype=np.float32)


def test_the_index_is_recreated_before_anything_is_uploaded(tmp_path: Path) -> None:
    store = FakeStore()

    build_index(store=store, embedder=_embed, manifest_path=tmp_path / "m.json")  # type: ignore[arg-type]

    assert store.events == ["recreate", *[f"upload {s}" for s in STRATEGIES]]


def test_every_chunk_carries_its_documents_title_url_and_strategy(tmp_path: Path) -> None:
    store = FakeStore()

    build_index(store=store, embedder=_embed, manifest_path=tmp_path / "m.json")  # type: ignore[arg-type]

    sources = {d.source.doc_id: d.source for d in ingest()}
    for strategy, chunks in store.uploads.items():
        assert {c.strategy for c in chunks} == {strategy}
        assert {c.doc_id for c in chunks} == set(sources)
        for chunk in chunks:
            assert chunk.title == sources[chunk.doc_id].title
            assert chunk.source_url == sources[chunk.doc_id].url


def test_every_chunk_carries_its_documents_region_type_and_date(tmp_path: Path) -> None:
    store = FakeStore()

    build_index(store=store, embedder=_embed, manifest_path=tmp_path / "m.json")  # type: ignore[arg-type]

    sources = {d.source.doc_id: d.source for d in ingest()}
    for chunks in store.uploads.values():
        for chunk in chunks:
            source = sources[chunk.doc_id]
            assert chunk.jurisdiction == source.jurisdiction
            assert chunk.source_type == source.source_type
            assert chunk.published == (source.published or "")  # "" when the source has no date


def test_the_chunks_are_exactly_what_the_chunker_makes_from_the_cleaned_text() -> None:
    documents = ingest()

    got = chunk_corpus(documents, "structure_aware")

    expected = [
        c
        for d in documents
        for c in chunk_document(
            d.text,
            doc_id=d.source.doc_id,
            strategy="structure_aware",
            chunk_size=CHUNK_WORDS,
            overlap=OVERLAP,
            max_sentences=MAX_SENTENCES,
        )
    ]
    assert [c.text for c in got] == [c.text for c in expected]


def test_the_record_of_what_was_indexed_matches_the_corpus(tmp_path: Path) -> None:
    store = FakeStore()
    record = tmp_path / "azure_index_manifest.json"
    documents = ingest()

    counts = build_index(store=store, embedder=_embed, documents=documents, manifest_path=record)  # type: ignore[arg-type]

    saved = json.loads(record.read_text(encoding="utf-8"))
    assert saved["corpus_sha256"] == corpus_sha256(documents)
    assert saved["chunks_per_strategy"] == counts
    assert all(count > 0 for count in counts.values())


def test_a_subset_of_strategies_uploads_only_those(tmp_path: Path) -> None:
    store = FakeStore()

    counts = build_index(
        store=store,  # type: ignore[arg-type]
        embedder=_embed,
        strategies=["fixed"],
        manifest_path=tmp_path / "m.json",
    )

    assert list(counts) == ["fixed"]
    assert store.events == ["recreate", "upload fixed"]
