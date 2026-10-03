"""Chunking strategies for the payments RAG corpus.

Four strategies share one goal (turn a document into retrievable pieces) and differ in how much
document structure they respect:

* fixed: a sliding window of words. Ignores structure; the baseline.
* recursive: split by markdown headings, then paragraphs, then fall back to word windows.
* semantic: group neighbouring sentences that share a payments topic. This is a keyword-topic
  heuristic, not an embedding model (see ``chunk_text_semantic``).
* structure_aware: like recursive, but keeps the full heading path, list items and tables intact.

Every strategy except ``fixed`` re-attaches the section heading to each piece, so a chunk still says
what it is about when it is retrieved on its own.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

STRATEGIES = ("fixed", "recursive", "semantic", "structure_aware")

_HEADING = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")
_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")

DEFAULT_TOPICS: dict[str, frozenset[str]] = {
    "authorization": frozenset(
        [
            "authorization",
            "authorisation",
            "authorize",
            "authorise",
            "authorized",
            "auth",
            "verify",
            "verifies",
            "verification",
            "valid",
            "approval",
            "approved",
        ]
    ),
    "settlement": frozenset(
        [
            "settlement",
            "settled",
            "settle",
            "funds",
            "transfer",
            "clearing",
            "cleared",
            "reconciled",
            "reconciliation",
            "processing",
            "processed",
        ]
    ),
    "dispute": frozenset(
        [
            "dispute",
            "disputes",
            "chargeback",
            "chargebacks",
            "claim",
            "issuer",
            "review",
            "reviews",
            "decision",
            "investigation",
            "investigate",
        ]
    ),
    "payment": frozenset(
        [
            "payment",
            "payments",
            "transaction",
            "transactions",
            "merchant",
            "card",
            "network",
            "acquirer",
        ]
    ),
    "messaging": frozenset(
        [
            "iso",
            "message",
            "messages",
            "messaging",
            "remittance",
            "format",
            "structured",
            "standard",
        ]
    ),
    "security": frozenset(
        ["authentication", "fraud", "security", "secure", "risk", "compliance", "resilience"]
    ),
}


@dataclass(frozen=True)
class Chunk:
    """A chunk of text plus the metadata needed to cite its source."""

    text: str
    chunk_index: int
    doc_id: str = ""
    section: str = ""  # heading path, e.g. "ISO 20022 overview > Why it matters"
    source_url: str = ""
    strategy: str = ""
    title: str = ""

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class _Section:
    headings: tuple[tuple[int, str], ...]  # (level, title) from the document root down
    body: str


@dataclass(frozen=True)
class _Piece:
    text: str
    section: str


def chunk_text(text: str, chunk_size: int = 250, overlap: int = 50) -> list[str]:
    """Split text into fixed-size word chunks with overlap.

    The chunking is intentionally simple: it uses whitespace-split words, so line breaks and
    markdown structure are flattened into single spaces. It is the baseline the others beat.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step

    return chunks


def strip_sections(text: str, titles: Iterable[str]) -> str:
    """Remove sections (a heading and everything under it, subsections included) by title.

    Use it at ingestion to drop meta sections such as "Example questions this helps answer": a chunk
    that merely lists a question matches that question's words without containing the answer.
    """
    drop = {title.lower() for title in titles}
    kept: list[str] = []
    skip_level: int | None = None
    for line in text.splitlines():
        match = _HEADING.match(line.strip())
        if match:
            level = len(match.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and match.group(2).lower() in drop:
                skip_level = level
        if skip_level is None:
            kept.append(line)
    return "\n".join(kept)


def _parse_sections(text: str) -> list[_Section]:
    """Split markdown into sections: a heading path plus the body text under it."""
    sections: list[_Section] = []
    stack: list[tuple[int, str]] = []
    body_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(body_lines).strip()
        if body:
            sections.append(_Section(tuple(stack), body))
        body_lines.clear()

    for line in text.splitlines():
        match = _HEADING.match(line.strip())
        if match:
            flush()
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2)))
        else:
            body_lines.append(line.rstrip())
    flush()
    return sections


def _heading_lines(headings: tuple[tuple[int, str], ...], full_path: bool) -> list[str]:
    chosen = headings if full_path else headings[-1:]
    return [f"{'#' * level} {title}" for level, title in chosen]


def _section_path(headings: tuple[tuple[int, str], ...]) -> str:
    return " > ".join(title for _, title in headings)


def _join(prefix: list[str], body: str) -> str:
    return "\n".join([*prefix, body])


def _blocks(body: str) -> list[str]:
    """Paragraph-level blocks (separated by blank lines); lists and tables stay in one block."""
    return [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]


def _list_items(block: str) -> list[str]:
    items: list[list[str]] = []
    for line in block.splitlines():
        if _BULLET.match(line) or not items:
            items.append([line.strip()])
        else:
            items[-1].append(line.strip())
    return ["\n".join(item) for item in items]


def _structure_units(block: str) -> list[str]:
    """Smallest pieces structure-aware chunking will not split: list items, a table, a paragraph."""
    first = block.splitlines()[0]
    if first.strip().startswith("|"):
        return [block]
    if _BULLET.match(first):
        return _list_items(block)
    return [block]


def _pack(units: list[str], budget: int, overlap: int) -> list[str]:
    """Greedily pack units into chunks of at most ``budget`` words; split oversized units."""
    out: list[str] = []
    current: list[str] = []
    used = 0
    for unit in units:
        size = len(unit.split())
        if size > budget:
            if current:
                out.append("\n".join(current))
                current, used = [], 0
            out.extend(chunk_text(unit, chunk_size=budget, overlap=overlap))
            continue
        if current and used + size > budget:
            out.append("\n".join(current))
            current, used = [], 0
        current.append(unit)
        used += size
    if current:
        out.append("\n".join(current))
    return out


def _recursive_pieces(text: str, chunk_size: int, overlap: int) -> list[_Piece]:
    pieces: list[_Piece] = []
    for section in _parse_sections(text):
        prefix = _heading_lines(section.headings, full_path=False)
        path = _section_path(section.headings)
        for body in _pack(_blocks(section.body), chunk_size, overlap):
            pieces.append(_Piece(_join(prefix, body), path))
    return pieces


def _sentences(body: str) -> list[str]:
    sentences: list[str] = []
    for block in _blocks(body):
        if _BULLET.match(block.splitlines()[0]):
            sentences.extend(_BULLET.sub("", " ".join(item.split())) for item in _list_items(block))
        else:
            flat = " ".join(block.split())
            sentences.extend(part for part in re.split(r"(?<=[.!?])\s+", flat) if part)
    return sentences


def _topics_for(sentence: str, topics: dict[str, frozenset[str]]) -> frozenset[str]:
    words = {word.lower() for word in re.findall(r"[A-Za-z0-9]+", sentence)}
    found = frozenset(name for name, keywords in topics.items() if words & keywords)
    return found or frozenset({"general"})


def _semantic_pieces(
    text: str,
    max_sentences: int,
    threshold: float,
    topics: dict[str, frozenset[str]],
) -> list[_Piece]:
    pieces: list[_Piece] = []
    for section in _parse_sections(text):
        prefix = _heading_lines(section.headings, full_path=False)
        path = _section_path(section.headings)
        group: list[str] = []
        group_topics: frozenset[str] = frozenset()
        for sentence in _sentences(section.body):
            sentence_topics = _topics_for(sentence, topics)
            if group:
                shared = len(group_topics & sentence_topics) / len(group_topics | sentence_topics)
                if len(group) >= max_sentences or (threshold > 0 and shared < threshold):
                    pieces.append(_Piece(_join(prefix, " ".join(group)), path))
                    group, group_topics = [], frozenset()
            group.append(sentence)
            group_topics |= sentence_topics
        if group:
            pieces.append(_Piece(_join(prefix, " ".join(group)), path))
    return pieces


def _structure_pieces(text: str, max_words: int) -> list[_Piece]:
    pieces: list[_Piece] = []
    for section in _parse_sections(text):
        prefix = _heading_lines(section.headings, full_path=True)
        path = _section_path(section.headings)
        units = [unit for block in _blocks(section.body) for unit in _structure_units(block)]
        for body in _pack(units, max_words, max_words // 4):
            pieces.append(_Piece(_join(prefix, body), path))
    return pieces


def chunk_text_recursive(text: str, chunk_size: int = 250, overlap: int = 0) -> list[str]:
    """Split by headings, then paragraphs, then word windows; keep the nearest heading.

    Paragraphs are packed together up to ``chunk_size`` words (heading not counted). A paragraph
    longer than that is cut into overlapping word windows, and nothing is dropped.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("chunk_size must be greater than overlap")
    return [piece.text for piece in _recursive_pieces(text, chunk_size, overlap)]


def chunk_text_semantic(
    text: str,
    max_chunk_size: int = 3,
    similarity_threshold: float = 0.15,
    topics: dict[str, frozenset[str]] | None = None,
) -> list[str]:
    """Group adjacent sentences that share a payments topic. ``max_chunk_size`` counts sentences.

    This is a keyword-topic heuristic, not an embedding model. Each sentence is tagged with topics
    from ``DEFAULT_TOPICS`` (authorization, settlement, dispute, ...). A sentence joins the current
    group when the Jaccard overlap of their topic sets is at least ``similarity_threshold``; a
    threshold of 0 merges everything up to ``max_chunk_size``. Swap in sentence embeddings later.
    """
    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be a positive integer")
    if not 0 <= similarity_threshold <= 1:
        raise ValueError("similarity_threshold must be between 0 and 1")
    pieces = _semantic_pieces(
        text, max_chunk_size, similarity_threshold, DEFAULT_TOPICS if topics is None else topics
    )
    return [piece.text for piece in pieces]


def chunk_text_structure_aware(text: str, max_chunk_size: int = 80) -> list[str]:
    """Keep the full heading path, list items and tables intact; ``max_chunk_size`` counts words.

    Every chunk starts with its whole heading path (``# Doc`` then ``## Section``). Bullet items and
    tables are never split mid-item unless a single one exceeds ``max_chunk_size`` words.
    """
    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be a positive integer")
    return [piece.text for piece in _structure_pieces(text, max_chunk_size)]


def chunk_document(
    text: str,
    *,
    doc_id: str,
    strategy: str,
    title: str = "",
    source_url: str = "",
    chunk_size: int = 80,
    overlap: int = 20,
    max_sentences: int = 4,
) -> list[Chunk]:
    """Chunk one document with the named strategy and attach source metadata to every chunk."""
    if strategy == "fixed":
        pieces = [_Piece(piece, "") for piece in chunk_text(text, chunk_size, overlap)]
    elif strategy == "recursive":
        pieces = _recursive_pieces(text, chunk_size, overlap)
    elif strategy == "semantic":
        pieces = _semantic_pieces(text, max_sentences, 0.15, DEFAULT_TOPICS)
    elif strategy == "structure_aware":
        pieces = _structure_pieces(text, chunk_size)
    else:
        raise ValueError(f"unknown strategy {strategy!r}; choose from {STRATEGIES}")
    return [
        Chunk(piece.text, index, doc_id, piece.section, source_url, strategy, title)
        for index, piece in enumerate(pieces)
    ]


def _chunk_metrics(chunks: list[str]) -> dict[str, float | int]:
    if not chunks:
        return {
            "chunk_count": 0,
            "avg_words_per_chunk": 0.0,
            "max_words_per_chunk": 0,
            "min_words_per_chunk": 0,
        }

    word_counts = [len(chunk.split()) for chunk in chunks]
    return {
        "chunk_count": len(chunks),
        "avg_words_per_chunk": sum(word_counts) / len(word_counts),
        "max_words_per_chunk": max(word_counts),
        "min_words_per_chunk": min(word_counts),
    }


def compare_chunking_strategies(
    text: str,
    chunk_size: int = 250,
    overlap: int = 50,
    max_chunk_size: int = 12,
    max_sentences: int = 3,
) -> dict[str, dict[str, float | int]]:
    """Return a metric summary for each chunking strategy so they can be compared directly.

    ``max_chunk_size`` is a word budget for structure-aware chunks; ``max_sentences`` is the
    sentence budget for semantic chunks (the two are different units).
    """
    return {
        "fixed": _chunk_metrics(chunk_text(text, chunk_size=chunk_size, overlap=overlap)),
        "recursive": _chunk_metrics(
            chunk_text_recursive(text, chunk_size=chunk_size, overlap=min(overlap, chunk_size - 1))
        ),
        "semantic": _chunk_metrics(chunk_text_semantic(text, max_chunk_size=max_sentences)),
        "structure_aware": _chunk_metrics(
            chunk_text_structure_aware(text, max_chunk_size=max_chunk_size)
        ),
    }
