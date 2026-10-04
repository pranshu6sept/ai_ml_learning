"""Scripted stand-ins for the model and the search, shared by the graph tests."""

from __future__ import annotations

from collections import deque
from typing import Any

from payments_rag import Hit
from payments_rag.chunking import Chunk
from payments_rag.grounding import Answerability
from payments_rag.structured import CitedAnswer, QueryRewrite, Route

PASSAGE = "pacs.008 is the FI to FI customer credit transfer message."


def hit(text: str = PASSAGE, doc: str = "iso", section: str = "ISO > pacs") -> Hit:
    return Hit(Chunk(text, 0, doc_id=doc, section=section, source_url="http://x"), 1.0)


def route(label: str = "in_scope") -> Route:
    return Route(label=label, reason="test")  # type: ignore[arg-type]


def good_answer() -> CitedAnswer:
    return CitedAnswer(
        answer="pacs.008 moves a credit transfer [1].", citations=[1], confidence="high"
    )


FULL = Answerability("full", PASSAGE, True)
PARTIAL = Answerability("partial", "", False)
NONE = Answerability("none", "", False)


class FakeSearch:
    """Returns the scripted result lists in order, then the last one again."""

    def __init__(self, *results: list[Hit]) -> None:
        self._results = list(results)
        self.queries: list[str] = []
        self.filters: list[Any] = []  # the filters given with each search, None when none

    def search(self, query: str, top_k: int = 3, filters: Any = None) -> list[Hit]:
        self.queries.append(query)
        self.filters.append(filters)
        index = min(len(self.queries) - 1, len(self._results) - 1)
        return self._results[index]


class FakeChat:
    """Pops scripted replies per kind of call. Items that are exceptions are raised instead."""

    def __init__(
        self,
        routes: list[Any] | None = None,
        grades: list[Any] | None = None,
        rewrites: list[Any] | None = None,
        drafts: list[Any] | None = None,
        plans: list[Any] | None = None,
    ) -> None:
        self.queues: dict[str, deque[Any]] = {
            "plan": deque(plans if plans is not None else []),
            "route": deque(routes if routes is not None else [route()]),
            "grade": deque(grades if grades is not None else [FULL]),
            "rewrite": deque(rewrites if rewrites is not None else [QueryRewrite(query="better")]),
            "draft": deque(drafts if drafts is not None else [good_answer()]),
        }
        self.calls: list[str] = []

    def _pop(self, kind: str) -> Any:
        self.calls.append(kind)
        item = self.queues[kind].popleft()
        if isinstance(item, Exception):
            raise item
        return item

    def complete_structured(self, prompt: str, model: type) -> Any:
        kind = {Route: "route", QueryRewrite: "rewrite", CitedAnswer: "draft"}[model]
        return self._pop(kind)

    def check_answerability(self, question: str, evidence: Any) -> Answerability:
        result: Answerability = self._pop("grade")
        return result

    def plan_search(self, prompt: str) -> Any:
        return self._pop("plan")


class RateLimitError(Exception):
    """Named like the OpenAI SDK's error so the retry policy treats it as transient."""
