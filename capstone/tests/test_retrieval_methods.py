import math

import pytest

from payments_rag import Retriever


def test_bm25_score_matches_a_hand_calculation() -> None:
    # N=2, "alpha" is in 1 chunk: idf = ln(1 + (2 - 1 + 0.5) / (1 + 0.5)) = ln 2.
    # Chunk 0 has tf=1, length 2 = average length, so the length factor is 1 and the
    # saturation term is tf * (k1 + 1) / (tf + k1) = 2.5 / 2.5 = 1.
    retriever = Retriever(["alpha beta", "beta gamma"], method="bm25")

    hits = retriever.search("alpha", top_k=2)

    assert [h.chunk.text for h in hits] == ["alpha beta"]
    assert hits[0].score == pytest.approx(math.log(2))


def test_bm25_prefers_the_shorter_chunk_for_the_same_term_count() -> None:
    filler = " ".join(f"filler{i}" for i in range(40))
    retriever = Retriever([f"pacs {filler}", "pacs identifies a business area"], method="bm25")

    hits = retriever.search("pacs", top_k=2)

    assert hits[0].chunk.text == "pacs identifies a business area"


def test_bm25_saturates_repeated_terms() -> None:
    retriever = Retriever(["fraud " * 10, "fraud", "unrelated words here"], method="bm25")

    ten, one = (h.score for h in retriever.search("fraud", top_k=2))

    assert ten < 3 * one  # ten mentions are far from ten times as relevant


@pytest.mark.parametrize("method", ["tfidf", "bm25"])
def test_stemming_matches_different_forms_of_a_word(method: str) -> None:
    chunks = ["Who it applies to: merchants and acquirers", "Settlement moves funds"]

    assert Retriever(chunks, method=method).search("Who does it apply to?") == []
    stemmed = Retriever(chunks, method=method, stem=True).search("Who does it apply to?")
    assert [h.chunk.text for h in stemmed] == [chunks[0]]


@pytest.mark.parametrize("method", ["tfidf", "bm25"])
def test_no_shared_terms_means_no_hits(method: str) -> None:
    retriever = Retriever(["settlement moves funds"], method=method, stem=True)

    assert retriever.search("quantum chromodynamics") == []


def test_unknown_method_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown method"):
        Retriever(["text"], method="magic")
