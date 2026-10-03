from payments_rag.chunking import (
    chunk_text,
    chunk_text_recursive,
    chunk_text_semantic,
    chunk_text_structure_aware,
    compare_chunking_strategies,
)


def test_fixed_size_chunking_keeps_overlap() -> None:
    text = "one two three four five six seven eight nine ten eleven twelve"

    chunks = chunk_text(text, chunk_size=5, overlap=2)

    assert chunks[0] == "one two three four five"
    assert chunks[1] == "four five six seven eight"
    assert chunks[2] == "seven eight nine ten eleven"
    assert chunks[3] == "ten eleven twelve"


def test_recursive_chunking_keeps_headings_together() -> None:
    text = "# Overview\nThis is the first paragraph.\n\n## Details\nThis is the second paragraph."

    chunks = chunk_text_recursive(text, chunk_size=12, overlap=0)

    assert any("Overview" in chunk and "first paragraph" in chunk for chunk in chunks)
    assert any("Details" in chunk and "second paragraph" in chunk for chunk in chunks)


def test_semantic_chunking_groups_related_sentences() -> None:
    text = (
        "Authorization verifies the card is valid. "
        "Settlement moves funds after processing. "
        "A dispute can happen when a customer challenges a payment. "
        "The issuer reviews the claim before a decision."
    )

    chunks = chunk_text_semantic(text, max_chunk_size=2)

    assert len(chunks) >= 2
    assert any("Authorization" in chunk and "valid" in chunk for chunk in chunks)
    assert any("Settlement" in chunk and "funds" in chunk for chunk in chunks)
    assert any("dispute" in chunk.lower() and "issuer" in chunk.lower() for chunk in chunks)


def test_structure_aware_chunking_keeps_headers_and_bullets() -> None:
    text = (
        "# Payment lifecycle\n"
        "- Authorization checks validity.\n"
        "- Clearing reconciles transactions.\n\n"
        "## Disputes\n"
        "A dispute is when a customer challenges a payment."
    )

    chunks = chunk_text_structure_aware(text, max_chunk_size=12)

    assert any("Payment lifecycle" in chunk for chunk in chunks)
    assert any("Authorization" in chunk and "Clearing" in chunk for chunk in chunks)
    assert any("Disputes" in chunk and "customer challenges" in chunk for chunk in chunks)


def test_compare_chunking_strategies_returns_metric_summary() -> None:
    text = (
        "# Payment lifecycle\n"
        "Authorization checks whether the card is valid.\n\n"
        "Settlement moves funds after processing.\n\n"
        "## Disputes\n"
        "A dispute happens when a customer challenges a transaction."
    )

    summary = compare_chunking_strategies(text, chunk_size=8, overlap=2, max_chunk_size=8)

    assert set(summary) == {"fixed", "recursive", "semantic", "structure_aware"}
    assert summary["fixed"]["chunk_count"] >= 1
    assert summary["recursive"]["avg_words_per_chunk"] > 0
    assert summary["structure_aware"]["chunk_count"] >= 1
