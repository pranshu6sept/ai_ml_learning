import json
from pathlib import Path

import pytest

from payments_rag import STRATEGIES, chunk_document, strip_sections
from payments_rag.ingestion import (
    META_SECTIONS,
    RegistryError,
    build_manifest,
    clean_text,
    ingest,
    load_registry,
    manifest_differences,
    write_manifest,
)

REAL_CORPUS = Path(__file__).resolve().parents[1] / "docs" / "corpus"


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": "doc-a",
        "title": "Doc A",
        "source_type": "x",
        "jurisdiction": "global",
        "url": "https://example.org/a",
        "file": "raw/a.md",
        "status": "available",
        "verification": "fetched",
        "published": "2025-01-02",
        "retrieved": "2026-10-03",
    }
    entry.update(overrides)
    return entry


def _corpus(tmp_path: Path, entries: list[dict[str, object]], files: dict[str, str]) -> Path:
    (tmp_path / "raw").mkdir()
    (tmp_path / "sources.json").write_text(json.dumps(entries), encoding="utf-8")
    for name, text in files.items():
        (tmp_path / "raw" / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_the_real_registry_is_valid_and_every_document_is_ingested() -> None:
    documents = ingest()

    assert len(documents) >= 11
    assert all(d.text.endswith("\n") and d.words > 50 for d in documents)
    assert {d.source.doc_id for d in documents} >= {"faqs", "pci_dss_overview"}


def test_registry_problems_are_all_reported_together(tmp_path: Path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            _entry(),
            _entry(id="doc-a", file="raw/missing.md"),  # duplicate id and a missing file
            _entry(id="doc-b", file="raw/b.md", verification="made_up", published="02/01/2025"),
            _entry(id="doc-c", file="raw/c.md", status="repealed"),  # repealed with no replacement
            _entry(id="doc-d", file="raw/d.md", retrieved=None),  # fetched but no date
            _entry(id="doc-e", file="raw/e.md", url="internal_draft"),  # not author-written, no URL
        ],
        {
            "a.md": "# A\n",
            "b.md": "# B\n",
            "c.md": "# C\n",
            "d.md": "# D\n",
            "e.md": "# E\n",
            "orphan.md": "# O\n",
        },
    )

    with pytest.raises(RegistryError) as error:
        load_registry(corpus)

    message = str(error.value)
    for expected in (
        "duplicate id 'doc-a'",
        "'raw/missing.md' does not exist",
        "unknown verification 'made_up'",
        "published '02/01/2025' is not YYYY-MM-DD",
        "repealed but 'superseded_by'",
        "doc-d: fetched from the web but has no 'retrieved' date",
        "doc-e: needs a public https URL",
        "raw/orphan.md is not registered",
    ):
        assert expected in message, expected


def test_a_planned_document_without_a_file_is_skipped_not_an_error(tmp_path: Path) -> None:
    corpus = _corpus(
        tmp_path,
        [
            _entry(),
            _entry(id="doc-p", file=None, status="planned", verification="via_search_summary"),
        ],
        {"a.md": "# A\n\nText.\n"},
    )

    assert [d.id for d in load_registry(corpus)] == ["doc-a"]


def test_cleaning_normalises_whitespace_and_drops_meta_sections() -> None:
    raw = (
        "﻿# Title\r\n\r\n\r\n\r\nBody with trailing spaces.   \r\n\r\n"
        "## Practical RAG relevance\r\n\r\nNotes for the learner.\r\n\r\n"
        "## Real section\r\n\r\nKept.\r\n"
    )

    cleaned = clean_text(raw)

    assert cleaned == "# Title\n\nBody with trailing spaces.\n\n## Real section\n\nKept.\n"
    assert clean_text(cleaned) == cleaned  # idempotent


def test_cleaning_keeps_every_gold_phrase_of_every_question() -> None:
    documents = {d.source.doc_id: " ".join(d.text.split()).lower() for d in ingest()}
    for path in sorted((REAL_CORPUS.parents[1] / "evals").glob("questions*.json")):
        for question in json.loads(path.read_text(encoding="utf-8")):
            for gold in question["gold"]:
                phrase = " ".join(gold["phrase"].split()).lower()
                assert phrase in documents[gold["doc"]], (path.name, question["id"])


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_ingestion_does_not_change_what_the_chunkers_produce(strategy: str) -> None:
    """The evaluation scripts chunk strip_sections(raw); ingestion must give the same chunks."""
    for d in ingest():
        via_ingestion = chunk_document(d.text, doc_id=d.source.doc_id, strategy=strategy)
        via_old_path = chunk_document(
            strip_sections(d.raw, META_SECTIONS), doc_id=d.source.doc_id, strategy=strategy
        )
        assert [c.text for c in via_ingestion] == [c.text for c in via_old_path], d.source.id


def test_the_manifest_hashes_change_when_a_document_changes(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path, [_entry()], {"a.md": "# A\n\nFirst version of the text here.\n"})
    before = build_manifest(ingest(corpus))

    (corpus / "raw" / "a.md").write_text(
        "# A\n\nSecond version of the text here.\n", encoding="utf-8"
    )
    after = build_manifest(ingest(corpus))

    assert before["corpus_sha256"] != after["corpus_sha256"]
    assert before["documents"][0]["sha256_text"] != after["documents"][0]["sha256_text"]


def test_a_stale_manifest_names_what_changed(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path, [_entry()], {"a.md": "# A\n\nFirst version of the text here.\n"})
    assert manifest_differences(corpus) == [
        "no manifest yet: run `python -m payments_rag.ingestion`"
    ]
    write_manifest(corpus)
    assert manifest_differences(corpus) == []

    (corpus / "raw" / "a.md").write_text(
        "# A\n\nEdited text, so the hash differs.\n", encoding="utf-8"
    )

    assert manifest_differences(corpus) == ["changed: doc-a"]


def test_the_committed_manifest_matches_the_documents() -> None:
    """Fails when a document is edited without running `uv run python -m payments_rag.ingestion`."""
    assert manifest_differences(REAL_CORPUS) == []
