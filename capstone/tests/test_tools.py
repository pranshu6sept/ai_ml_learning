import json
from types import SimpleNamespace
from typing import Any

import pytest

from payments_rag import AzureChatGenerator, AzureHybridRetriever, AzureSettings, SearchFilter
from payments_rag.structured import StructuredOutputError, parse
from payments_rag.tools import TOOL_NAME, SearchCorpus, to_filter, tool_choice, tool_definition

SETTINGS = AzureSettings("https://o", "emb", "chat", "https://s")


def _args(**fields: Any) -> SearchCorpus:
    base: dict[str, Any] = {
        "query": "authentication",
        "jurisdictions": [],
        "published_from": None,
        "published_to": None,
    }
    return SearchCorpus(**{**base, **fields})


def test_the_tool_is_offered_as_a_strict_function_and_forced() -> None:
    definition = tool_definition()["function"]

    assert definition["name"] == TOOL_NAME and definition["strict"] is True
    schema = definition["parameters"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"query", "jurisdictions", "published_from", "published_to"}
    assert schema["properties"]["jurisdictions"]["items"]["enum"] == ["EU", "India", "US", "global"]
    assert tool_choice() == {"type": "function", "function": {"name": TOOL_NAME}}


def test_the_model_cannot_invent_a_region() -> None:
    raw = json.dumps(
        {"query": "x", "jurisdictions": ["Mars"], "published_from": None, "published_to": None}
    )

    with pytest.raises(StructuredOutputError):
        parse(SearchCorpus, raw)


def test_arguments_become_a_search_filter_with_duplicates_removed() -> None:
    flt = to_filter(_args(jurisdictions=["India", "India", "EU"], published_from="2025-01-01"))

    assert flt == SearchFilter(jurisdictions=("India", "EU"), published_from="2025-01-01")


def test_a_date_that_is_not_year_month_day_is_dropped_not_trusted() -> None:
    flt = to_filter(_args(published_from="last year", published_to="2025-13-45x"))

    assert flt.published_from is None and flt.published_to is None


class _ToolClient:
    def __init__(self, tool_calls: Any) -> None:
        self.sent: list[dict[str, Any]] = []
        self.tool_calls = tool_calls
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs: Any) -> Any:
        self.sent.append(kwargs)
        message = SimpleNamespace(content=None, tool_calls=self.tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _call(name: str, arguments: dict[str, Any]) -> Any:
    return [SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))]


def test_plan_search_sends_the_tool_forces_it_and_returns_validated_arguments() -> None:
    arguments = {
        "query": "authentication directions",
        "jurisdictions": ["India"],
        "published_from": "2025-01-01",
        "published_to": None,
    }
    client = _ToolClient(_call(TOOL_NAME, arguments))

    args = AzureChatGenerator(SETTINGS, client=client).plan_search("plan this")

    assert args.jurisdictions == ["India"] and args.published_from == "2025-01-01"
    assert client.sent[0]["tools"][0]["function"]["name"] == TOOL_NAME
    assert client.sent[0]["tool_choice"]["function"]["name"] == TOOL_NAME


@pytest.mark.parametrize("calls", [None, [], _call("delete_everything", {})])
def test_plan_search_refuses_a_reply_that_did_not_call_the_tool(calls: Any) -> None:
    with pytest.raises(StructuredOutputError, match="did not call"):
        AzureChatGenerator(SETTINGS, client=_ToolClient(calls)).plan_search("plan this")


def test_plan_search_rejects_arguments_that_do_not_fit_the_schema() -> None:
    bad = _call(TOOL_NAME, {"query": "x", "jurisdictions": "India"})

    with pytest.raises(StructuredOutputError):
        AzureChatGenerator(SETTINGS, client=_ToolClient(bad)).plan_search("plan this")


def test_a_per_call_filter_overrides_the_one_the_retriever_was_built_with() -> None:
    seen: list[Any] = []

    class Store:
        def search(self, query: str, vector: Any, **kwargs: Any) -> list[Any]:
            seen.append(kwargs["filters"])
            return []

    embedder = lambda texts: [[0.0]]  # noqa: E731
    built = SearchFilter(doc_ids=("psd2_overview",))
    retriever = AzureHybridRetriever(Store(), embedder, "structure_aware", filters=built)  # type: ignore[arg-type]

    retriever.search("q")
    retriever.search("q", 3, filters=SearchFilter(jurisdictions=("EU",)))

    assert seen == [built, SearchFilter(jurisdictions=("EU",))]
