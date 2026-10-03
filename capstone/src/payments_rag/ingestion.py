"""Corpus ingestion: validate the document registry, clean each document, record what was ingested.

``sources.json`` is the registry: one entry per document with its title, URL, dates and how well it
was verified. ``load_registry`` refuses to proceed if the registry and the files disagree,
``clean_text`` turns a raw markdown file into the text that gets chunked, and ``manifest.json``
records a hash of every raw and cleaned document so a change is detectable (for example, a
document edited but the search index not rebuilt).

Run from the repo root:
    uv run python -m payments_rag.ingestion                # write processed/manifest.json
    uv run python -m payments_rag.ingestion --check        # fail if documents changed since then
    uv run python -m payments_rag.ingestion --check-index  # does the Azure index match the corpus?

What this cannot do: decide that a document is public or non-confidential. The registry requires a
source URL for everything except author-written documents, and the README rule (public material
only) remains a human responsibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .chunking import strip_sections

CORPUS_DIR = Path(__file__).resolve().parents[2] / "docs" / "corpus"
INDEX_MANIFEST = Path(__file__).resolve().parents[2] / "evals" / "azure_index_manifest.json"

# Sections that describe the corpus or list sample questions. They are not knowledge, and a
# chunk that lists a question can outrank the chunk that answers it, so ingestion removes them.
META_SECTIONS = ("Practical RAG relevance", "Example questions this helps answer")

VERIFICATION_LEVELS = frozenset(
    {
        "fetched",
        "fetched_and_search_summary",
        "via_search_summary",
        "author_written_unverified",
        "author_written_cross_checked",
        "author_written_partly_verified",
    }
)
REQUIRED_FIELDS = (
    "id",
    "title",
    "source_type",
    "jurisdiction",
    "url",
    "file",
    "status",
    "verification",
    "published",
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class RegistryError(ValueError):
    """The registry and the files on disk disagree. The message lists every problem found."""


@dataclass(frozen=True)
class SourceDocument:
    """One entry of ``sources.json``."""

    id: str
    title: str
    source_type: str
    jurisdiction: str
    url: str
    file: str
    status: str
    verification: str
    published: str | None
    retrieved: str | None
    superseded_by: str | None
    notes: str
    checked_against: tuple[str, ...]

    @property
    def doc_id(self) -> str:
        """The file stem, which evaluation questions and chunks use to name the document."""
        return Path(self.file).stem


@dataclass(frozen=True)
class IngestedDocument:
    """A registry entry with its raw text and the cleaned text that will be chunked."""

    source: SourceDocument
    raw: str
    text: str

    @property
    def sha256_raw(self) -> str:
        return hashlib.sha256(self.raw.encode("utf-8")).hexdigest()

    @property
    def sha256_text(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def words(self) -> int:
        return len(self.text.split())


def _problems(entries: list[dict[str, Any]], corpus_dir: Path) -> list[str]:
    problems: list[str] = []
    ids = [str(e.get("id")) for e in entries]
    files = [str(e["file"]) for e in entries if e.get("file")]
    for name in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate id {name!r}")
    for name in sorted({f for f in files if files.count(f) > 1}):
        problems.append(f"file {name!r} is registered more than once")
    for entry in entries:
        label = str(entry.get("id", "<no id>"))
        for field in REQUIRED_FIELDS:
            if field not in entry:
                problems.append(f"{label}: missing field {field!r}")
        file = entry.get("file")
        if not file and entry.get("status") != "planned":
            problems.append(f"{label}: no file, and status is not 'planned'")
        elif file and not (corpus_dir / file).is_file():
            problems.append(f"{label}: file {file!r} does not exist")
        if entry.get("verification") not in VERIFICATION_LEVELS:
            problems.append(f"{label}: unknown verification {entry.get('verification')!r}")
        for field in ("published", "retrieved"):
            value = entry.get(field)
            if value is not None and not _DATE.fullmatch(str(value)):
                problems.append(f"{label}: {field} {value!r} is not YYYY-MM-DD")
        if str(entry.get("verification", "")).startswith(
            ("fetched", "via_search")
        ) and not entry.get("retrieved"):
            problems.append(f"{label}: fetched from the web but has no 'retrieved' date")
        if entry.get("status") == "repealed" and entry.get("superseded_by") not in ids:
            problems.append(f"{label}: repealed but 'superseded_by' names no registered document")
        url = str(entry.get("url", ""))
        if not url.startswith("https://") and not str(entry.get("verification", "")).startswith(
            "author_written"
        ):
            problems.append(
                f"{label}: needs a public https URL (only author-written documents may lack one)"
            )
    registered = set(files)
    for path in sorted((corpus_dir / "raw").glob("*.md")):
        if f"raw/{path.name}" not in registered:
            problems.append(f"raw/{path.name} is not registered in sources.json")
    return problems


def load_registry(corpus_dir: Path = CORPUS_DIR) -> list[SourceDocument]:
    """Read ``sources.json`` and check it against the files. Documents still planned are skipped."""
    entries: list[dict[str, Any]] = json.loads((corpus_dir / "sources.json").read_text("utf-8"))
    problems = _problems(entries, corpus_dir)
    if problems:
        raise RegistryError("registry problems:\n- " + "\n- ".join(problems))
    return [
        SourceDocument(
            id=e["id"],
            title=e["title"],
            source_type=e["source_type"],
            jurisdiction=e["jurisdiction"],
            url=e["url"],
            file=e["file"],
            status=e["status"],
            verification=e["verification"],
            published=e["published"],
            retrieved=e.get("retrieved"),
            superseded_by=e.get("superseded_by"),
            notes=e.get("notes", ""),
            checked_against=tuple(e.get("checked_against", ())),
        )
        for e in entries
        if e.get("file")
    ]


def clean_text(text: str, drop_sections: tuple[str, ...] = META_SECTIONS) -> str:
    """Turn raw markdown into the text that is chunked.

    Removes a byte-order mark, normalises line endings, strips trailing spaces, drops the meta
    sections, and collapses runs of blank lines. It does not rewrite words, so a gold phrase in
    the raw document is still in the cleaned one. Cleaning twice gives the same result.
    """
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = strip_sections(text, drop_sections)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n") + "\n"


def ingest(
    corpus_dir: Path = CORPUS_DIR, drop_sections: tuple[str, ...] = META_SECTIONS
) -> list[IngestedDocument]:
    """Validate the registry, then read and clean every registered document."""
    documents = []
    for source in load_registry(corpus_dir):
        raw = (corpus_dir / source.file).read_text(encoding="utf-8")
        documents.append(IngestedDocument(source, raw, clean_text(raw, drop_sections)))
    return documents


def corpus_sha256(documents: list[IngestedDocument]) -> str:
    """One hash for the whole cleaned corpus (order-independent)."""
    joined = "\n".join(
        f"{d.source.id}:{d.sha256_text}" for d in sorted(documents, key=lambda d: d.source.id)
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_manifest(documents: list[IngestedDocument]) -> dict[str, Any]:
    return {
        "corpus_sha256": corpus_sha256(documents),
        "documents": [
            {
                "id": d.source.id,
                "file": d.source.file,
                "title": d.source.title,
                "status": d.source.status,
                "verification": d.source.verification,
                "published": d.source.published,
                "retrieved": d.source.retrieved,
                "words": d.words,
                "sha256_raw": d.sha256_raw,
                "sha256_text": d.sha256_text,
            }
            for d in sorted(documents, key=lambda d: d.source.id)
        ],
    }


def write_manifest(corpus_dir: Path = CORPUS_DIR) -> Path:
    path = corpus_dir / "processed" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(ingest(corpus_dir))
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def manifest_differences(corpus_dir: Path = CORPUS_DIR) -> list[str]:
    """What changed since the manifest was written: an empty list means it is current."""
    path = corpus_dir / "processed" / "manifest.json"
    if not path.is_file():
        return ["no manifest yet: run `python -m payments_rag.ingestion`"]
    old = {d["id"]: d for d in json.loads(path.read_text("utf-8"))["documents"]}
    new = {d["id"]: d for d in build_manifest(ingest(corpus_dir))["documents"]}
    changes = [f"added: {i}" for i in sorted(new.keys() - old.keys())]
    changes += [f"removed: {i}" for i in sorted(old.keys() - new.keys())]
    changes += [
        f"changed: {i}"
        for i in sorted(new.keys() & old.keys())
        if new[i]["sha256_text"] != old[i]["sha256_text"]
    ]
    return changes


def write_index_manifest(
    documents: Sequence[IngestedDocument],
    chunks_per_strategy: dict[str, int],
    path: Path = INDEX_MANIFEST,
) -> Path:
    """Record which corpus the Azure index was built from (called by the index builder)."""
    path.write_text(
        json.dumps(
            {
                "corpus_sha256": corpus_sha256(list(documents)),
                "chunks_per_strategy": chunks_per_strategy,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def index_matches_corpus(corpus_dir: Path = CORPUS_DIR) -> bool | None:
    """True if the recorded index matches the current corpus, False if not, None if unrecorded."""
    if not INDEX_MANIFEST.is_file():
        return None
    recorded = json.loads(INDEX_MANIFEST.read_text("utf-8"))["corpus_sha256"]
    return bool(recorded == corpus_sha256(ingest(corpus_dir)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and ingest the payments corpus.")
    parser.add_argument(
        "--check", action="store_true", help="fail if documents changed since the manifest"
    )
    parser.add_argument(
        "--check-index", action="store_true", help="check the Azure index against the corpus"
    )
    args = parser.parse_args(argv)
    try:
        documents = ingest()
    except RegistryError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        f"registry ok: {len(documents)} documents, "
        f"{sum(d.words for d in documents):,} words after cleaning"
    )
    if args.check_index:
        state = index_matches_corpus()
        print(
            {
                True: "Azure index matches the corpus",
                False: "Azure index is STALE: rebuild it",
                None: "no index record yet",
            }[state]
        )
        return 0 if state else 1
    if args.check:
        changes = manifest_differences()
        print(
            "manifest is current"
            if not changes
            else "manifest is stale:\n- " + "\n- ".join(changes)
        )
        return 1 if changes else 0
    print(f"wrote {write_manifest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
