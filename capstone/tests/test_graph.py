"""The compiled graph end to end with a scripted model and search (needs LangGraph)."""

import pytest
from graph_fakes import (
    FULL,
    NONE,
    PARTIAL,
    FakeChat,
    FakeSearch,
    RateLimitError,
    good_answer,
    hit,
    route,
)

pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from payments_rag.graph import Deps, build_graph, resume, run_graph  # noqa: E402
from payments_rag.grounding import NO_ANSWER  # noqa: E402
from payments_rag.structured import CitedAnswer, QueryRewrite  # noqa: E402

BAD = CitedAnswer(answer="It moves a transfer.", citations=[], confidence="high")


def _graph(chat: FakeChat, search: FakeSearch | None = None, **options: object) -> object:
    return build_graph(Deps(search or FakeSearch([hit()]), chat), retry_wait=0.0, **options)  # type: ignore[arg-type]


def test_a_supported_question_goes_route_retrieve_grade_generate_validate() -> None:
    result = run_graph(_graph(FakeChat()), "What is pacs.008?")

    assert not result.answer.refused
    assert result.answer.text == "pacs.008 moves a credit transfer [1]."
    assert result.answer.sources == ("[1] iso > ISO > pacs (http://x)",)
    assert result.trace == ("route:in_scope", "retrieve:1", "grade:full", "generate", "validate:ok")


def test_an_out_of_scope_question_is_declined_without_any_search() -> None:
    search = FakeSearch([hit()])

    result = run_graph(_graph(FakeChat(routes=[route("out_of_scope")]), search), "Who won the cup?")

    assert result.answer.refused and search.queries == []
    assert result.trace == ("route:out_of_scope", "decline")


def test_small_talk_gets_a_greeting_not_a_refusal_and_no_search() -> None:
    search = FakeSearch([hit()])

    result = run_graph(_graph(FakeChat(routes=[route("chit_chat")]), search), "Hello!")

    assert not result.answer.refused and search.queries == []
    assert result.trace == ("route:chit_chat", "small_talk")


def test_weak_evidence_triggers_one_rewrite_then_succeeds() -> None:
    chat = FakeChat(grades=[NONE, FULL], rewrites=[QueryRewrite(query="customer credit transfer")])
    search = FakeSearch([hit("Unrelated.")], [hit()])

    result = run_graph(_graph(chat, search), "What moves money?")

    assert search.queries == ["What moves money?", "customer credit transfer"]
    assert not result.answer.refused
    assert result.trace == (
        "route:in_scope", "retrieve:1", "grade:none", "rewrite",
        "retrieve:1", "grade:full", "generate", "validate:ok",
    )  # fmt: skip


def test_the_rewrite_is_bounded_to_one_then_the_graph_refuses() -> None:
    chat = FakeChat(grades=[NONE, NONE, NONE])
    search = FakeSearch([hit("Unrelated.")])

    result = run_graph(_graph(chat, search), "What is the penalty?")

    assert result.answer.refused and result.answer.text == NO_ANSWER
    assert len(search.queries) == 2  # the original query and one rewrite, never a third
    assert chat.calls.count("rewrite") == 1 and "draft" not in chat.calls
    assert result.trace[-1] == "refuse"


def test_a_bad_draft_is_regenerated_once_with_feedback() -> None:
    chat = FakeChat(drafts=[BAD, good_answer()])

    result = run_graph(_graph(chat), "What is pacs.008?")

    assert not result.answer.refused
    assert any(step.startswith("validate:fail") for step in result.trace)
    assert result.trace[-2:] == ("regenerate", "validate:ok")
    assert chat.calls.count("draft") == 2


def test_two_bad_drafts_end_in_a_refusal_that_says_validation_failed() -> None:
    chat = FakeChat(drafts=[BAD, BAD])

    result = run_graph(_graph(chat), "What is pacs.008?")

    assert result.answer.refused
    assert "failed validation" in result.answer.reason
    assert chat.calls.count("draft") == 2  # no third attempt


def test_a_transient_model_error_is_retried_but_a_real_error_is_not() -> None:
    flaky = FakeChat(routes=[RateLimitError("429"), route()])

    result = run_graph(_graph(flaky), "What is pacs.008?")

    assert not result.answer.refused and flaky.calls.count("route") == 2

    broken = FakeChat(routes=[ValueError("bug")])
    with pytest.raises(ValueError, match="bug"):
        run_graph(_graph(broken), "What is pacs.008?")
    assert broken.calls == ["route"]


def test_human_review_needs_a_checkpointer() -> None:
    with pytest.raises(ValueError, match="checkpointer"):
        _graph(FakeChat(), review=True)


def test_partial_evidence_pauses_for_a_person_who_can_approve() -> None:
    chat = FakeChat(grades=[PARTIAL, PARTIAL])
    graph = _graph(chat, review=True, checkpointer=MemorySaver())

    paused = run_graph(graph, "What is pacs.008?", thread_id="t1")

    assert paused.interrupted is not None and paused.interrupted["grade"] == "partial"
    assert "draft" not in chat.calls  # nothing is generated while it waits

    done = resume(graph, "What is pacs.008?", "answer", thread_id="t1")

    assert not done.answer.refused and "review:answer" in done.trace


def test_a_person_can_decline_and_the_run_ends_in_a_refusal() -> None:
    chat = FakeChat(grades=[PARTIAL, PARTIAL])
    graph = _graph(chat, review=True, checkpointer=MemorySaver())

    run_graph(graph, "What is pacs.008?", thread_id="t2")
    done = resume(graph, "What is pacs.008?", "refuse", thread_id="t2")

    assert done.answer.refused and "human" in done.answer.reason


def test_review_only_triggers_for_partial_evidence_not_for_none() -> None:
    chat = FakeChat(grades=[NONE, NONE])
    graph = _graph(chat, review=True, checkpointer=MemorySaver())

    result = run_graph(graph, "What is pacs.008?", thread_id="t3")

    assert result.interrupted is None and result.answer.refused
