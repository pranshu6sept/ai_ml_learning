"""On the last attempt, a mostly good answer is repaired (uncited sentences dropped)."""

from typing import Any

import pytest
from graph_fakes import FakeChat, FakeSearch, hit

from payments_rag.graph import Deps, nodes
from payments_rag.structured import CitedAnswer

PARTLY_CITED = CitedAnswer(
    answer="pacs.008 moves a credit transfer [1]. It also makes payments safer.",
    citations=[1],
    confidence="medium",
)
UNCITED = CitedAnswer(answer="It moves a transfer.", citations=[1], confidence="low")


def _state(draft: CitedAnswer, regenerations: int) -> nodes.GraphState:
    state: nodes.GraphState = {
        "question": "What is pacs.008?",
        "hits": [nodes._hit_dict(hit())],
        "draft": draft.model_dump(),
        "regenerations": regenerations,
        "trace": [],
    }
    return state


def test_on_the_first_attempt_an_uncited_sentence_is_a_failure_to_regenerate() -> None:
    update = nodes.validate(_state(PARTLY_CITED, regenerations=0))

    assert update["valid"] is False and "no valid citation" in update["feedback"]


def test_on_the_last_attempt_the_uncited_sentence_is_dropped_and_the_rest_kept() -> None:
    update = nodes.validate(_state(PARTLY_CITED, regenerations=1))

    assert update["valid"] is True and update["refused"] is False
    assert update["reply"] == "pacs.008 moves a credit transfer [1]."
    assert update["sources"] == ["[1] iso > ISO > pacs (http://x)"]
    assert update["trace"][0].startswith("validate:repaired")


def test_repair_is_not_a_way_to_pass_an_answer_with_nothing_cited() -> None:
    update = nodes.validate(_state(UNCITED, regenerations=1))

    assert update["valid"] is False


def test_repair_does_not_hide_a_citation_to_a_passage_that_does_not_exist() -> None:
    wrong = CitedAnswer(answer="It moves a transfer [4].", citations=[4], confidence="low")

    update = nodes.validate(_state(wrong, regenerations=1))

    assert update["valid"] is False and "do not exist" in update["feedback"]


def test_through_the_graph_two_partly_cited_drafts_end_in_a_repaired_answer() -> None:
    pytest.importorskip("langgraph")
    from payments_rag.graph import build_graph, run_graph

    chat: Any = FakeChat(drafts=[PARTLY_CITED, PARTLY_CITED])
    graph = build_graph(Deps(FakeSearch([hit()]), chat), retry_wait=0.0)

    result = run_graph(graph, "What is pacs.008?")

    assert not result.answer.refused
    assert result.answer.text == "pacs.008 moves a credit transfer [1]."
    assert any(step.startswith("validate:repaired") for step in result.trace)
    assert chat.calls.count("draft") == 2  # still bounded: one regeneration, then repair


def test_when_most_sentences_would_be_dropped_the_answer_is_refused_not_repaired() -> None:
    mostly_uncited = CitedAnswer(
        answer="It is fast. It is cheap. It is safe. It moves a transfer [1].",
        citations=[1],
        confidence="low",
    )

    update = nodes.validate(_state(mostly_uncited, regenerations=1))

    assert update["valid"] is False
