"""The compiled graph with the planning (tool call) step switched on (needs LangGraph)."""

import pytest
from graph_fakes import FULL, NONE, FakeChat, FakeSearch, hit

pytest.importorskip("langgraph")

from payments_rag import SearchFilter  # noqa: E402
from payments_rag.graph import Deps, build_graph, run_graph  # noqa: E402
from payments_rag.structured import QueryRewrite  # noqa: E402
from payments_rag.tools import SearchCorpus  # noqa: E402


def _plan(query: str = "authentication", regions: list[str] | None = None) -> SearchCorpus:
    return SearchCorpus(
        query=query,
        jurisdictions=regions or [],  # type: ignore[arg-type]
        published_from=None,
        published_to=None,
    )


def test_planning_runs_between_route_and_retrieve_and_filters_the_search() -> None:
    search = FakeSearch([hit()])
    chat = FakeChat(plans=[_plan("RBI authentication", ["India"])])
    graph = build_graph(Deps(search, chat), plan_filters=True, retry_wait=0.0)

    result = run_graph(graph, "What does RBI require?")

    assert result.trace[:3] == ("route:in_scope", "plan:jurisdictions=['India']", "retrieve:1")
    assert search.queries == ["RBI authentication"]
    assert search.filters == [SearchFilter(jurisdictions=("India",))]
    assert not result.answer.refused


def test_without_planning_the_graph_does_not_call_the_tool() -> None:
    chat = FakeChat()
    graph = build_graph(Deps(FakeSearch([hit()]), chat), retry_wait=0.0)

    result = run_graph(graph, "What is pacs.008?")

    assert "plan" not in chat.calls and not any(step.startswith("plan") for step in result.trace)


def test_when_a_filtered_search_finds_nothing_good_the_retry_searches_without_filters() -> None:
    search = FakeSearch([hit("Unrelated.")], [hit()])
    chat = FakeChat(
        plans=[_plan("RBI authentication", ["India"])],
        grades=[NONE, FULL],
        rewrites=[QueryRewrite(query="authentication rules")],
    )
    graph = build_graph(Deps(search, chat), plan_filters=True, retry_wait=0.0)

    result = run_graph(graph, "What does RBI require?")

    assert search.filters == [SearchFilter(jurisdictions=("India",)), None]
    assert search.queries == ["RBI authentication", "authentication rules"]
    assert not result.answer.refused
