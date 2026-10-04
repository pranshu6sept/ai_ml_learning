import math

from payments_rag.metrics import ndcg_at_k, recall_at_k


def test_recall_is_the_share_of_gold_passages_covered() -> None:
    assert recall_at_k([True, False], k=3) == 0.5
    assert recall_at_k([True, True], k=3) == 1.0
    assert recall_at_k([False], k=3) == 0.0


def test_a_question_with_no_gold_passage_has_no_recall() -> None:
    assert math.isnan(recall_at_k([], k=3))


def test_a_perfect_ordering_has_ndcg_one() -> None:
    assert ndcg_at_k([True, True, False], total_relevant=2, k=3) == 1.0


def test_the_same_relevant_chunk_scores_lower_the_further_down_it_is() -> None:
    first = ndcg_at_k([True, False, False], total_relevant=1, k=3)
    second = ndcg_at_k([False, True, False], total_relevant=1, k=3)
    third = ndcg_at_k([False, False, True], total_relevant=1, k=3)

    assert first == 1.0
    assert math.isclose(second, 1 / math.log2(3))  # 0.631
    assert math.isclose(third, 0.5)
    assert first > second > third


def test_nothing_relevant_in_the_top_k_scores_zero() -> None:
    assert ndcg_at_k([False, False, False], total_relevant=2, k=3) == 0.0


def test_a_relevant_chunk_beyond_k_does_not_count() -> None:
    assert ndcg_at_k([False, False, False, True], total_relevant=1, k=3) == 0.0


def test_the_best_possible_score_is_capped_by_k() -> None:
    # Five relevant chunks exist but only three fit: three at the top is perfect.
    assert ndcg_at_k([True, True, True], total_relevant=5, k=3) == 1.0


def test_with_no_relevant_chunk_anywhere_ndcg_is_undefined() -> None:
    assert math.isnan(ndcg_at_k([False], total_relevant=0, k=3))
