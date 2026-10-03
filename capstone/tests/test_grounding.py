from collections.abc import Sequence

import numpy as np
import pytest

from payments_rag import (
    NO_ANSWER,
    Chunk,
    Hit,
    Retriever,
    build_prompt,
    choose_threshold,
    rerank,
    retrieve_evidence,
)

CHUNKS = [
    Chunk("PSD2 bans retailer surcharges for card use.", 0, "psd2", "PSD2 > Fees", "https://eu"),
    Chunk("Settlement moves funds between banks.", 1, "card", "Lifecycle", "https://card"),
    Chunk("A dispute is a customer challenge.", 2, "faq", "FAQ 5", "https://faq"),
]


def word_overlap_reranker(query: str, texts: Sequence[str]) -> np.ndarray:
    """A stand-in reranker: the number of query words a text contains, minus one."""
    words = {w.strip("?.,").lower() for w in query.split()}
    return np.array([len(words & {w.strip("?.,").lower() for w in t.split()}) - 1.0 for t in texts])


def test_rerank_orders_by_the_reranker_and_carries_its_scores() -> None:
    hits = [Hit(CHUNKS[1], 0.9), Hit(CHUNKS[0], 0.1)]

    ranked = rerank("retailer surcharges for card use", hits, word_overlap_reranker)

    assert [h.chunk.doc_id for h in ranked] == ["psd2", "card"]
    assert ranked[0].score == pytest.approx(4.0)  # 5 shared words minus 1
    assert rerank("anything", [], word_overlap_reranker) == []


def test_evidence_is_returned_with_citations_when_the_score_clears_the_threshold() -> None:
    retriever = Retriever(CHUNKS, method="bm25")

    answer = retrieve_evidence(
        "Does PSD2 ban retailer surcharges for card use?",
        retriever,
        word_overlap_reranker,
        threshold=2.0,
    )

    assert not answer.abstained
    assert answer.evidence[0].chunk.doc_id == "psd2"
    assert answer.citations()[0] == "[1] psd2 > PSD2 > Fees (https://eu)"


def test_a_score_below_the_threshold_means_abstain_and_no_evidence_is_passed_on() -> None:
    retriever = Retriever(CHUNKS, method="bm25")

    answer = retrieve_evidence(
        "What is a dispute?", retriever, word_overlap_reranker, threshold=5.0
    )

    assert answer.abstained
    assert answer.evidence == ()
    assert "below the threshold" in answer.reason
    assert build_prompt(answer) == f"Reply exactly: {NO_ANSWER}"


def test_nothing_matching_the_question_also_means_abstain() -> None:
    retriever = Retriever(CHUNKS, method="bm25")

    answer = retrieve_evidence(
        "quantum chromodynamics", retriever, word_overlap_reranker, threshold=0
    )

    assert answer.abstained
    assert answer.reason == "nothing in the corpus matched the question"


def test_prompt_numbers_the_passages_and_forbids_outside_knowledge() -> None:
    retriever = Retriever(CHUNKS, method="bm25")
    answer = retrieve_evidence(
        "Does PSD2 ban retailer surcharges?", retriever, word_overlap_reranker, threshold=1.0
    )

    prompt = build_prompt(answer)

    assert "ONLY the numbered passages" in prompt
    assert "[1] PSD2 bans retailer surcharges for card use." in prompt
    assert NO_ANSWER in prompt
    assert prompt.endswith("Question: Does PSD2 ban retailer surcharges?")


def test_choose_threshold_splits_cleanly_separated_scores_in_the_middle() -> None:
    assert choose_threshold([5.0, 6.0, 7.0], [1.0, 2.0, 3.0]) == pytest.approx(4.0)


def test_choose_threshold_balances_the_two_kinds_of_error_when_scores_overlap() -> None:
    answerable = [1.0, 4.0, 5.0, 6.0, 7.0]
    unanswerable = [0.0, 0.5, 2.0, 4.5]

    cut = choose_threshold(answerable, unanswerable)

    # Cutting at 4.75 answers 3 of 5 answerable and refuses all 4 unanswerable: balanced
    # accuracy 0.8,
    # the best any cut-off reaches here.
    assert cut == pytest.approx(4.75)
