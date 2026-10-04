# ruff: noqa: E501
"""The steps of the question-answering graph, as plain functions (no LangGraph import here).

Each node takes the current state and returns only the fields it changes. Keeping them plain makes
them testable with a fake model and a fake search, and lets ``build.py`` do nothing but wiring.

    route -> retrieve -> grade -> generate -> validate -> done
       |         ^         |                      |
       |         +-rewrite-+ (once)              +-> generate again (once) -> refuse if still bad
       +-> decline (out of scope) / small talk (chit chat)
                           +-> human review (optional, when the evidence is only partial)

State holds plain dicts and strings (no custom classes) so it can be saved by a checkpointer.
"""

from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from typing import Annotated, Any, Protocol, TypedDict

from ..chunking import Chunk
from ..grounding import NO_ANSWER, Answerability, enforce_citations
from ..retrieval import Hit
from ..search_filters import SearchFilter
from ..structured import CitedAnswer, ModelT, QueryRewrite, Route
from ..tools import SearchCorpus, to_filter

MAX_REWRITES = 1  # one bounded retry of the search with a rewritten query
MAX_REGENERATIONS = 1  # one bounded retry of the answer when validation fails
TOP_K = 3

OUT_OF_SCOPE_REPLY = (
    "That is outside what I can help with. I answer questions about banking and payments "
    "(ISO 20022, card payments and disputes, PCI DSS, PSD2, RBI and UPI rules)."
)
CHIT_CHAT_REPLY = (
    "Hello! Ask me a question about banking and payments rules and I will answer from my "
    "documents, with sources."
)

ROUTER_PROMPT = """You route questions for a payments knowledge assistant. Its documents cover banking and payments: ISO 20022 messages, card payments and disputes, PCI DSS, PSD2, RBI and UPI rules, and US card billing disputes.
Choose one label:
- in_scope: a question about payments, banking, cards or their regulation. Everyday wording counts: questions about shops, merchants, cards, transfers, disputes or banks are in scope even without technical terms. Choose this even if you doubt the documents cover the detail; a later step checks that.
- out_of_scope: a question unrelated to payments or banking (sports, weather, programming, general trivia).
- chit_chat: a greeting, thanks, or a question about the assistant itself.

Question: {question}"""

PLAN_PROMPT = """Call the search_corpus tool for the question below.
- `query`: the topic as a short search query.
- `jurisdictions`: only if the question clearly names a region or regulator (RBI, NPCI, UPI, India -> India; PSD2, EU, EBA -> EU; CFPB, US -> US); otherwise an empty list. Do not guess.
- `published_from` / `published_to`: only if the question asks about a period or about what is current or recent; otherwise null.

Question: {question}"""

REWRITE_PROMPT = """A search for the question below did not find passages that fully answer it. Rewrite it as one short search query, using the words a payments document would use (spell out acronyms, add the likely key terms). Keep the meaning.

Question: {question}
Previous query: {query}"""

GENERATE_PROMPT = """Answer the question using ONLY the numbered passages below.
- State only what the passages say. Do not add explanations, benefits, examples or inferences of your own.
- End every sentence with a citation such as [1].
- In `citations`, list the passage numbers you used.
- Set `confidence` to high if the passages fully answer the question, medium if partly, low if barely.
- If the passages do not contain the answer, set `answer` to exactly: {no_answer} with no citations and confidence low.
{feedback}
Passages:
{passages}

Question: {question}"""


class ChatModel(Protocol):
    def complete_structured(self, prompt: str, model: type[ModelT]) -> ModelT: ...

    def check_answerability(self, question: str, evidence: Any) -> Answerability: ...

    def plan_search(self, prompt: str) -> SearchCorpus: ...


@dataclass(frozen=True)
class Deps:
    """What the nodes need from the outside world."""

    retriever: Any  # search(query, top_k), and search(query, top_k, filters=...) when planning
    chat: ChatModel


class GraphState(TypedDict, total=False):
    question: str
    route: str
    query: str
    filters: dict[str, Any]  # metadata filters chosen by the planning tool call; {} for none
    attempts: int  # search rewrites used
    regenerations: int  # answer regenerations used
    hits: list[dict[str, Any]]
    grade: str  # full / partial / none
    can_answer: bool
    review: str  # a human's decision: "answer" or "refuse"
    draft: dict[str, Any]
    feedback: str  # why the last draft failed validation
    valid: bool
    reply: str
    sources: list[str]
    refused: bool
    reason: str
    trace: Annotated[list[str], operator.add]


def _hit_dict(hit: Hit) -> dict[str, Any]:
    c = hit.chunk
    return {
        "doc_id": c.doc_id,
        "section": c.section,
        "source_url": c.source_url,
        "text": c.text,
        "score": hit.score,
    }


def to_hits(rows: list[dict[str, Any]]) -> tuple[Hit, ...]:
    return tuple(
        Hit(
            Chunk(
                r["text"],
                i,
                doc_id=r["doc_id"],
                section=r["section"],
                source_url=r["source_url"],
            ),
            float(r["score"]),
        )
        for i, r in enumerate(rows)
    )


def source_label(n: int, row: dict[str, Any]) -> str:
    return f"[{n}] {row['doc_id']} > {row['section'] or 'document'} ({row['source_url']})"


# --- nodes -----------------------------------------------------------------------------------


def route(state: GraphState, deps: Deps) -> dict[str, Any]:
    decision = deps.chat.complete_structured(
        ROUTER_PROMPT.format(question=state["question"]), Route
    )
    return {"route": decision.label, "trace": [f"route:{decision.label}"]}


def decline(state: GraphState) -> dict[str, Any]:
    return {
        "reply": OUT_OF_SCOPE_REPLY,
        "refused": True,
        "reason": "the question is outside the payments scope",
        "sources": [],
        "trace": ["decline"],
    }


def small_talk(state: GraphState) -> dict[str, Any]:
    return {
        "reply": CHIT_CHAT_REPLY,
        "refused": False,
        "reason": "chit chat",
        "sources": [],
        "trace": ["small_talk"],
    }


def plan(state: GraphState, deps: Deps) -> dict[str, Any]:
    """Let the model choose the search query and filters by calling the search_corpus tool."""
    args = deps.chat.plan_search(PLAN_PROMPT.format(question=state["question"]))
    flt = to_filter(args)
    filters = {
        key: value
        for key, value in (
            ("jurisdictions", list(flt.jurisdictions)),
            ("published_from", flt.published_from),
            ("published_to", flt.published_to),
        )
        if value
    }
    summary = ",".join(f"{k}={v}" for k, v in filters.items()) or "none"
    return {
        "query": args.query.strip() or state["question"],
        "filters": filters,
        "trace": [f"plan:{summary}"],
    }


def retrieve(state: GraphState, deps: Deps) -> dict[str, Any]:
    query = state.get("query") or state["question"]
    filters = state.get("filters")
    if filters:
        chosen = SearchFilter(
            jurisdictions=tuple(filters.get("jurisdictions", ())),
            published_from=filters.get("published_from"),
            published_to=filters.get("published_to"),
        )
        hits = deps.retriever.search(query, TOP_K, filters=chosen)
    else:
        hits = deps.retriever.search(query, TOP_K)
    return {"hits": [_hit_dict(h) for h in hits], "trace": [f"retrieve:{len(hits)}"]}


def grade(state: GraphState, deps: Deps) -> dict[str, Any]:
    """Do the passages fully answer the question? The model must quote a sentence, and code
    checks that the quote really is in the passages."""
    hits = to_hits(state["hits"])
    if not hits:
        return {"grade": "none", "can_answer": False, "trace": ["grade:none"]}
    verdict = deps.chat.check_answerability(state["question"], hits)
    return {
        "grade": verdict.label,
        "can_answer": verdict.can_answer,
        "trace": [f"grade:{verdict.label}"],
    }


def rewrite(state: GraphState, deps: Deps) -> dict[str, Any]:
    previous = state.get("query") or state["question"]
    new = deps.chat.complete_structured(
        REWRITE_PROMPT.format(question=state["question"], query=previous), QueryRewrite
    )
    return {
        "query": new.query.strip() or previous,
        "filters": {},  # a filter the model chose may be what hid the answer: search wider
        "attempts": state.get("attempts", 0) + 1,
        "trace": ["rewrite"],
    }


def generate(state: GraphState, deps: Deps) -> dict[str, Any]:
    rows = state["hits"]
    passages = "\n\n".join(f"[{n}] {r['text']}" for n, r in enumerate(rows, 1))
    feedback = state.get("feedback", "")
    note = f"\nYour previous answer was rejected: {feedback}. Fix that.\n" if feedback else ""
    draft = deps.chat.complete_structured(
        GENERATE_PROMPT.format(
            no_answer=NO_ANSWER, feedback=note, passages=passages, question=state["question"]
        ),
        CitedAnswer,
    )
    regenerations = state.get("regenerations", 0) + (1 if feedback else 0)
    return {
        "draft": draft.model_dump(),
        "regenerations": regenerations,
        "trace": ["generate" if not feedback else "regenerate"],
    }


def validate(state: GraphState) -> dict[str, Any]:
    """Check the draft is well formed, cited, and cites only passages that exist."""
    draft = CitedAnswer(**state["draft"])
    rows = state["hits"]
    n = len(rows)
    if draft.answer.strip() == NO_ANSWER:
        return {
            "valid": True,
            "reply": NO_ANSWER,
            "refused": True,
            "reason": "the model found no answer in the passages",
            "sources": [],
            "trace": ["validate:declined"],
        }
    problems = []
    if not draft.answer.strip():
        problems.append("the answer is empty")
    if not draft.citations:
        problems.append("no citations were listed")
    missing = sorted({c for c in draft.citations if not 1 <= c <= n})
    if missing:
        problems.append(f"citation numbers {missing} do not exist")
    cited = enforce_citations(draft.answer, n)
    if cited.dropped:
        problems.append(f"{len(cited.dropped)} sentence(s) have no valid citation")
    if cited.refused and not problems:
        problems.append("the answer carries no usable citation")
    only_uncited = problems == [f"{len(cited.dropped)} sentence(s) have no valid citation"]
    final_attempt = state.get("regenerations", 0) >= MAX_REGENERATIONS
    if only_uncited and final_attempt and not cited.refused:
        # The one regeneration is spent and the answer is otherwise sound: keep the cited
        # sentences and drop the uncited ones, rather than refusing the whole answer.
        used = sorted({int(m) for m in re.findall(r"\[(\d+)\]", cited.text)})
        return {
            "valid": True,
            "reply": cited.text,
            "refused": False,
            "reason": f"validated after dropping {len(cited.dropped)} uncited sentence(s)",
            "sources": [source_label(k, rows[k - 1]) for k in used if 1 <= k <= n],
            "trace": [f"validate:repaired ({len(cited.dropped)} uncited dropped)"],
        }
    if problems:
        text = "; ".join(problems)
        return {"valid": False, "feedback": text, "trace": [f"validate:fail ({text})"]}
    used = sorted({int(m) for m in re.findall(r"\[(\d+)\]", cited.text)})
    return {
        "valid": True,
        "reply": cited.text,
        "refused": False,
        "reason": f"validated; model confidence {draft.confidence}",
        "sources": [source_label(k, rows[k - 1]) for k in used if 1 <= k <= n],
        "trace": ["validate:ok"],
    }


def refuse(state: GraphState) -> dict[str, Any]:
    if state.get("valid") is False:
        reason = f"the answer failed validation: {state.get('feedback', '')}"
    elif state.get("review") == "refuse":
        reason = "a human reviewer declined to answer"
    else:
        reason = f"the passages were judged '{state.get('grade', 'none')}'"
    return {
        "reply": NO_ANSWER,
        "refused": True,
        "reason": reason,
        "sources": [],
        "trace": ["refuse"],
    }


def human_review(state: GraphState) -> dict[str, Any]:
    """Pause for a person when the evidence is only partial. Resume with "answer" or "refuse"."""
    from langgraph.types import interrupt

    decision = interrupt(
        {
            "question": state["question"],
            "grade": state.get("grade"),
            "passages": [r["text"] for r in state["hits"]],
            "ask": 'Answer from these passages? Resume with "answer" or "refuse".',
        }
    )
    return {
        "review": "answer" if decision == "answer" else "refuse",
        "trace": [f"review:{decision}"],
    }


# --- routing decisions ---------------------------------------------------------------------


def after_route(state: GraphState, *, planning: bool = False) -> str:
    return {"in_scope": "plan" if planning else "retrieve", "chit_chat": "small_talk"}.get(
        state["route"], "decline"
    )


def after_grade(state: GraphState, *, review: bool, max_rewrites: int = MAX_REWRITES) -> str:
    if state["can_answer"]:
        return "generate"
    if state.get("attempts", 0) < max_rewrites:
        return "rewrite"
    if review and state.get("grade") == "partial":
        return "human_review"
    return "refuse"


def after_review(state: GraphState) -> str:
    return "generate" if state.get("review") == "answer" else "refuse"


def after_validate(state: GraphState) -> str:
    if state.get("valid"):
        return "done"
    return "generate" if state.get("regenerations", 0) < MAX_REGENERATIONS else "refuse"
