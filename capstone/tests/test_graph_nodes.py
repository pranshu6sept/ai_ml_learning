"""The graph's steps and routing decisions, tested as plain functions (no LangGraph needed)."""

from typing import Any

import pytest
from graph_fakes import (
    FULL,
    NONE,
    PARTIAL,
    FakeChat,
    FakeSearch,
    good_answer,
    hit,
    route,
)

from payments_rag.graph import Deps, nodes
from payments_rag.grounding import NO_ANSWER
from payments_rag.structured import CitedAnswer, QueryRewrite


def _deps(chat: FakeChat | None = None, search: FakeSearch | None = None) -> Deps:
    return Deps(search or FakeSearch([hit()]), chat or FakeChat())  # type: ignore[arg-type]


def _state(**fields: Any) -> nodes.GraphState:
    base: nodes.GraphState = {
        "question": "What is pacs.008?",
        "query": "What is pacs.008?",
        "attempts": 0,
        "regenerations": 0,
        "hits": [nodes._hit_dict(hit())],
        "trace": [],
    }
    base.update(fields)  # type: ignore[typeddict-item]
    return base


def test_route_records_the_label_and_the_scope_decision_follows_it() -> None:
    update = nodes.route(_state(), _deps(FakeChat(routes=[route("out_of_scope")])))

    assert update["route"] == "out_of_scope"
    assert nodes.after_route({"route": "in_scope"}) == "retrieve"  # type: ignore[typeddict-item]
    assert nodes.after_route({"route": "chit_chat"}) == "small_talk"  # type: ignore[typeddict-item]
    assert nodes.after_route({"route": "out_of_scope"}) == "decline"  # type: ignore[typeddict-item]


def test_retrieve_searches_the_current_query_not_the_original_question() -> None:
    search = FakeSearch([hit()])

    update = nodes.retrieve(_state(query="credit transfer message"), _deps(search=search))

    assert search.queries == ["credit transfer message"]
    assert update["hits"][0]["doc_id"] == "iso"


def test_no_search_results_means_nothing_to_grade_and_no_model_call() -> None:
    chat = FakeChat()

    update = nodes.grade(_state(hits=[]), _deps(chat))

    assert update["grade"] == "none" and update["can_answer"] is False
    assert chat.calls == []


def test_grade_uses_the_quote_verified_verdict() -> None:
    assert nodes.grade(_state(), _deps(FakeChat(grades=[FULL])))["can_answer"] is True
    assert nodes.grade(_state(), _deps(FakeChat(grades=[PARTIAL])))["can_answer"] is False


def test_rewrite_changes_the_query_and_counts_the_attempt() -> None:
    chat = FakeChat(rewrites=[QueryRewrite(query="  customer credit transfer  ")])

    update = nodes.rewrite(_state(), _deps(chat))

    assert update["query"] == "customer credit transfer" and update["attempts"] == 1


@pytest.mark.parametrize(
    ("state", "review", "expected"),
    [
        ({"can_answer": True}, False, "generate"),
        ({"can_answer": False, "attempts": 0}, False, "rewrite"),
        ({"can_answer": False, "attempts": 1, "grade": "none"}, False, "refuse"),
        ({"can_answer": False, "attempts": 1, "grade": "partial"}, False, "refuse"),
        ({"can_answer": False, "attempts": 1, "grade": "partial"}, True, "human_review"),
        ({"can_answer": False, "attempts": 1, "grade": "none"}, True, "refuse"),
    ],
)
def test_after_grade_rewrites_once_then_reviews_or_refuses(
    state: dict[str, Any], review: bool, expected: str
) -> None:
    assert nodes.after_grade(state, review=review) == expected  # type: ignore[arg-type]


def test_generate_asks_for_a_cited_answer_and_stores_it_as_plain_data() -> None:
    update = nodes.generate(_state(), _deps())

    assert update["draft"]["citations"] == [1]
    assert update["regenerations"] == 0 and update["trace"] == ["generate"]


def test_generating_again_after_feedback_counts_as_a_regeneration() -> None:
    update = nodes.generate(_state(feedback="no citations were listed"), _deps())

    assert update["regenerations"] == 1 and update["trace"] == ["regenerate"]


def test_a_cited_answer_validates_and_lists_only_the_passages_it_cites() -> None:
    state = _state(
        hits=[nodes._hit_dict(hit()), nodes._hit_dict(hit("Other text.", "cards", "Cards"))],
        draft=good_answer().model_dump(),
    )

    update = nodes.validate(state)

    assert update["valid"] is True and update["refused"] is False
    assert update["sources"] == ["[1] iso > ISO > pacs (http://x)"]


@pytest.mark.parametrize(
    ("answer", "citations", "problem"),
    [
        ("It moves a transfer.", [], "no citations were listed"),
        ("It moves a transfer [3].", [3], "citation numbers [3] do not exist"),
        ("It moves a transfer [1]. It is fast.", [1], "no valid citation"),
        ("", [1], "the answer is empty"),
    ],
)
def test_a_draft_with_missing_or_wrong_citations_fails_validation(
    answer: str, citations: list[int], problem: str
) -> None:
    draft = CitedAnswer(answer=answer, citations=citations, confidence="high")

    update = nodes.validate(_state(draft=draft.model_dump()))

    assert update["valid"] is False
    assert problem in update["feedback"]


def test_a_model_that_declines_is_a_valid_refusal_not_a_validation_failure() -> None:
    draft = CitedAnswer(answer=NO_ANSWER, citations=[], confidence="low")

    update = nodes.validate(_state(draft=draft.model_dump()))

    assert update["valid"] is True and update["refused"] is True and update["reply"] == NO_ANSWER


def test_validation_failure_regenerates_once_then_refuses() -> None:
    assert nodes.after_validate({"valid": True}) == "done"  # type: ignore[typeddict-item]
    assert nodes.after_validate({"valid": False, "regenerations": 0}) == "generate"  # type: ignore[typeddict-item]
    assert nodes.after_validate({"valid": False, "regenerations": 1}) == "refuse"  # type: ignore[typeddict-item]


def test_refuse_says_why() -> None:
    assert "failed validation" in nodes.refuse(_state(valid=False, feedback="x"))["reason"]
    assert "'none'" in nodes.refuse(_state(grade="none"))["reason"]
    assert "human" in nodes.refuse(_state(review="refuse"))["reason"]
    assert nodes.refuse(_state(grade=NONE.label))["reply"] == NO_ANSWER


def test_state_survives_a_round_trip_through_plain_data() -> None:
    rows = [nodes._hit_dict(hit())]

    restored = nodes.to_hits(rows)

    assert restored[0].chunk.text == hit().chunk.text and restored[0].chunk.doc_id == "iso"
