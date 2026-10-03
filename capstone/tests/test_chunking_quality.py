"""Regression tests for chunking defects found in the Week 4 review."""

import pytest

from payments_rag import (
    chunk_document,
    chunk_text_recursive,
    chunk_text_semantic,
    chunk_text_structure_aware,
    strip_sections,
)

SPACED_HEADING = "# Settlement\n\nSettlement moves funds between banks after clearing is complete."


def test_recursive_keeps_every_word_of_a_long_section() -> None:
    words = " ".join(f"w{i}" for i in range(400))

    chunks = chunk_text_recursive(f"# Title\n{words}", chunk_size=50, overlap=0)

    body = " ".join(" ".join(chunk.splitlines()[1:]) for chunk in chunks).split()
    assert body == words.split()
    assert all(chunk.startswith("# Title\n") for chunk in chunks)


@pytest.mark.parametrize("chunker", [chunk_text_recursive, chunk_text_structure_aware])
def test_heading_is_not_split_from_its_body_by_a_blank_line(chunker) -> None:  # type: ignore[no-untyped-def]
    chunks = chunker(SPACED_HEADING, 40)

    assert len(chunks) == 1
    assert chunks[0].startswith("# Settlement\n")
    assert "moves funds" in chunks[0]


def test_structure_aware_keeps_the_full_heading_path() -> None:
    text = "# Doc\n\n## Section\n\nSome text about the section."

    assert chunk_text_structure_aware(text) == ["# Doc\n## Section\nSome text about the section."]


def test_structure_aware_never_splits_a_list_item() -> None:
    items = ["- alpha beta gamma delta", "- epsilon zeta eta theta", "- iota kappa lambda mu"]
    text = "# List\n\n" + "\n".join(items)

    chunks = chunk_text_structure_aware(text, max_chunk_size=9)

    body_lines = [line for chunk in chunks for line in chunk.splitlines()[1:]]
    assert body_lines == items
    assert len(chunks) == 3


def test_semantic_threshold_controls_merging() -> None:
    text = "Authorization is checked first. Settlement moves funds later."

    assert len(chunk_text_semantic(text, max_chunk_size=2, similarity_threshold=0)) == 1
    assert len(chunk_text_semantic(text, max_chunk_size=2, similarity_threshold=0.15)) == 2


def test_semantic_keeps_the_section_heading() -> None:
    text = "## Disputes\n\nA dispute is raised. The issuer reviews the claim."

    chunks = chunk_text_semantic(text, max_chunk_size=4)

    assert chunks == ["## Disputes\nA dispute is raised. The issuer reviews the claim."]


def test_chunk_document_attaches_source_metadata() -> None:
    text = "# Card summary\n\n## Core concepts\n\n- Issuer: the bank that issued the card."

    chunks = chunk_document(
        text,
        doc_id="card",
        strategy="structure_aware",
        title="Card summary",
        source_url="https://example.org/card",
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert (chunk.doc_id, chunk.chunk_index, chunk.strategy) == ("card", 0, "structure_aware")
    assert chunk.section == "Card summary > Core concepts"
    assert chunk.source_url == "https://example.org/card"
    assert chunk.title == "Card summary"


def test_chunk_document_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        chunk_document("text", doc_id="d", strategy="magic")


def test_strip_sections_removes_a_section_and_its_children_only() -> None:
    text = (
        "# Doc\n\n## Keep\n\nuseful\n\n## Drop me\n\nnoise\n\n### Child\n\nmore noise\n\n"
        "## Also keep\n\nuseful too"
    )

    cleaned = strip_sections(text, ["drop me"])

    assert "noise" not in cleaned
    assert "useful" in cleaned
    assert "useful too" in cleaned
    assert "## Keep" in cleaned and "## Also keep" in cleaned
