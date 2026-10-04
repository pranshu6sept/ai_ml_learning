"""Wire the nodes into a LangGraph graph and run it.

LangGraph is imported only here (and in ``nodes.human_review``), so the rest of the package works
without it. Install it with ``uv sync --group orchestration``.

What LangGraph adds over a plain function that calls the steps in order:

* **state** with a reducer: every node returns just the fields it changes, and ``trace`` appends;
* **conditional edges**: the next node is chosen from the state (``after_grade`` and friends);
* **retry policy**: a transient model error (rate limit, timeout) re-runs just that node;
* **human in the loop**: ``interrupt`` pauses the run and saves its state in a checkpointer;
  ``resume`` continues it later, possibly in another process if the checkpointer is durable.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from ..ask import Answer
from .nodes import (
    MAX_REWRITES,
    Deps,
    GraphState,
    after_grade,
    after_review,
    after_route,
    after_validate,
    decline,
    generate,
    grade,
    human_review,
    plan,
    refuse,
    retrieve,
    rewrite,
    route,
    small_talk,
    to_hits,
    validate,
)

_TRANSIENT = {"RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError"}


def is_transient(error: Exception) -> bool:
    """True for errors worth retrying: rate limits, timeouts, connection and server errors."""
    return type(error).__name__ in _TRANSIENT or isinstance(error, TimeoutError | ConnectionError)


@dataclass(frozen=True)
class GraphResult:
    """The outcome of one run: the answer, the path taken, and a pending human decision if any."""

    answer: Answer
    trace: tuple[str, ...]
    interrupted: dict[str, Any] | None = None


def build_graph(
    deps: Deps,
    *,
    review: bool = False,
    max_rewrites: int = MAX_REWRITES,
    plan_filters: bool = False,
    checkpointer: Any | None = None,
    retry_wait: float = 2.0,
) -> Any:
    """Compile the graph. ``review=True`` pauses for a person when the evidence is only partial
    (this needs a ``checkpointer`` so the run can be resumed). ``plan_filters=True`` adds a step
    in which the model chooses the query and metadata filters by calling a tool."""
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import RetryPolicy

    if review and checkpointer is None:
        raise ValueError("human review needs a checkpointer so the paused run can be resumed")
    retry = RetryPolicy(max_attempts=3, initial_interval=retry_wait, retry_on=is_transient)

    graph = StateGraph(GraphState)
    # Nodes that call the model get the retry policy; the others cannot fail transiently.
    graph.add_node("route", partial(route, deps=deps), retry_policy=retry)
    if plan_filters:
        graph.add_node("plan", partial(plan, deps=deps), retry_policy=retry)
        graph.add_edge("plan", "retrieve")
    graph.add_node("retrieve", partial(retrieve, deps=deps), retry_policy=retry)
    graph.add_node("grade", partial(grade, deps=deps), retry_policy=retry)
    graph.add_node("rewrite", partial(rewrite, deps=deps), retry_policy=retry)
    graph.add_node("generate", partial(generate, deps=deps), retry_policy=retry)
    graph.add_node("validate", validate)
    graph.add_node("decline", decline)
    graph.add_node("small_talk", small_talk)
    graph.add_node("refuse", refuse)
    graph.add_node("human_review", human_review)

    graph.add_edge(START, "route")
    first = "plan" if plan_filters else "retrieve"
    graph.add_conditional_edges(
        "route", partial(after_route, planning=plan_filters), [first, "decline", "small_talk"]
    )
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        partial(after_grade, review=review, max_rewrites=max_rewrites),
        ["generate", "rewrite", "human_review", "refuse"],
    )
    graph.add_edge("rewrite", "retrieve")
    graph.add_conditional_edges("human_review", after_review, ["generate", "refuse"])
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges(
        "validate", after_validate, {"done": END, "generate": "generate", "refuse": "refuse"}
    )
    for final in ("decline", "small_talk", "refuse"):
        graph.add_edge(final, END)
    return graph.compile(checkpointer=checkpointer)


def _result(question: str, output: dict[str, Any]) -> GraphResult:
    pending = output.get("__interrupt__")
    if pending:
        value = pending[0].value if hasattr(pending[0], "value") else pending[0]
        answer = Answer(question, "", (), False, "waiting for a human decision", ())
        return GraphResult(answer, tuple(output.get("trace", ())), dict(value))
    answer = Answer(
        question,
        output["reply"],
        tuple(output.get("sources", ())),
        bool(output["refused"]),
        output.get("reason", ""),
        to_hits(output.get("hits", [])),
    )
    return GraphResult(answer, tuple(output.get("trace", ())))


def run_graph(graph: Any, question: str, *, thread_id: str | None = None) -> GraphResult:
    """Run one question through the graph. ``thread_id`` names the run for a checkpointer."""
    config = {"configurable": {"thread_id": thread_id}} if thread_id else None
    initial: GraphState = {
        "question": question,
        "query": question,
        "attempts": 0,
        "regenerations": 0,
        "trace": [],
    }
    return _result(question, graph.invoke(initial, config))


def resume(graph: Any, question: str, decision: str, *, thread_id: str) -> GraphResult:
    """Continue a run that paused for human review, with "answer" or "refuse"."""
    from langgraph.types import Command

    config = {"configurable": {"thread_id": thread_id}}
    return _result(question, graph.invoke(Command(resume=decision), config))
