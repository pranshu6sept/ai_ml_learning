"""The planning step (tool call that picks query and filters), tested without LangGraph."""

from typing import Any

from graph_fakes import FakeChat, FakeSearch, hit

from payments_rag import SearchFilter
from payments_rag.graph import Deps, nodes
from payments_rag.structured import QueryRewrite
from payments_rag.tools import SearchCorpus


def _plan(**fields: Any) -> SearchCorpus:
    base: dict[str, Any] = {
        "query": "authentication directions",
        "jurisdictions": [],
        "published_from": None,
        "published_to": None,
    }
    return SearchCorpus(**{**base, **fields})


def _state(**fields: Any) -> nodes.GraphState:
    base: nodes.GraphState = {"question": "What did RBI require in 2025?", "trace": []}
    base.update(fields)  # type: ignore[typeddict-item]
    return base


def test_plan_takes_the_query_and_only_the_filters_the_model_set() -> None:
    chat = FakeChat(plans=[_plan(jurisdictions=["India"], published_from="2025-01-01")])

    update = nodes.plan(_state(), Deps(FakeSearch([hit()]), chat))

    assert update["query"] == "authentication directions"
    assert update["filters"] == {"jurisdictions": ["India"], "published_from": "2025-01-01"}
    assert update["trace"] == ["plan:jurisdictions=['India'],published_from=2025-01-01"]


def test_plan_with_no_filters_leaves_the_filter_state_empty() -> None:
    update = nodes.plan(_state(), Deps(FakeSearch([hit()]), FakeChat(plans=[_plan()])))

    assert update["filters"] == {} and update["trace"] == ["plan:none"]


def test_plan_falls_back_to_the_question_when_the_model_returns_an_empty_query() -> None:
    update = nodes.plan(_state(), Deps(FakeSearch([hit()]), FakeChat(plans=[_plan(query="  ")])))

    assert update["query"] == "What did RBI require in 2025?"


def test_plan_drops_a_malformed_date_the_model_produced() -> None:
    update = nodes.plan(
        _state(), Deps(FakeSearch([hit()]), FakeChat(plans=[_plan(published_from="recently")]))
    )

    assert "published_from" not in update["filters"]


def test_retrieve_passes_the_chosen_filters_to_the_search() -> None:
    search = FakeSearch([hit()])
    state = _state(query="q", filters={"jurisdictions": ["EU"], "published_from": "2025-01-01"})

    nodes.retrieve(state, Deps(search, FakeChat()))

    assert search.filters == [SearchFilter(jurisdictions=("EU",), published_from="2025-01-01")]


def test_retrieve_without_filters_does_not_pass_any() -> None:
    search = FakeSearch([hit()])

    nodes.retrieve(_state(query="q", filters={}), Deps(search, FakeChat()))

    assert search.filters == [None]


def test_the_rewrite_drops_the_filters_so_the_second_search_is_wider() -> None:
    chat = FakeChat(rewrites=[QueryRewrite(query="widened")])

    update = nodes.rewrite(
        _state(filters={"jurisdictions": ["India"]}), Deps(FakeSearch([hit()]), chat)
    )

    assert update["filters"] == {} and update["query"] == "widened"


def test_with_planning_on_an_in_scope_question_goes_to_plan_first() -> None:
    assert nodes.after_route({"route": "in_scope"}, planning=True) == "plan"  # type: ignore[typeddict-item]
    assert nodes.after_route({"route": "in_scope"}) == "retrieve"  # type: ignore[typeddict-item]
    assert nodes.after_route({"route": "out_of_scope"}, planning=True) == "decline"  # type: ignore[typeddict-item]
