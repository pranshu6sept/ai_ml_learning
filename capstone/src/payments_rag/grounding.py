"""The grounding rule: answer only from retrieved evidence, cite it, abstain when there is none."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from . import prompts
from .reranking import Reranker, rerank
from .retrieval import Hit, Retriever

NO_ANSWER = "I don't know based on the provided documents."
# The prompts live in `payments_rag/prompts/*.txt` (see there for why).
STRICT_CITATION_RULE = prompts.load("strict_citation_rule").rstrip("\n") + " "
_CITATION = re.compile(r"\[(\d+)\]")
_TRAILING_CITATION = re.compile(r"([.!?])\s*((?:\[\d+\]\s*)+)(?=\s|$)")
# An inline numbered list ("steps: 1. A. 2. B [1].") is kept as ONE sentence, so a
# single citation at its end covers the list. Items on separate lines are still separate sentences.
_LIST_MARKER = re.compile(r"(?:^|(?<=\n)|(?<=[:;.!?] ))(\d{1,2})\.(?=\s+[A-Z])")
_ONLY_CITATIONS = re.compile(r"^\s*(?:\[\d+\]\s*)+[.!?]?\s*$")


@dataclass(frozen=True)
class GroundedAnswer:
    """What the retrieval stage hands to a language model: evidence to answer from, or a refusal."""

    question: str
    abstained: bool
    evidence: tuple[Hit, ...]
    reason: str

    def citations(self) -> list[str]:
        """One label per evidence chunk: ``[1] doc_id > section (url)``."""
        return [
            f"[{n}] {h.chunk.doc_id} > {h.chunk.section or 'document'} ({h.chunk.source_url})"
            for n, h in enumerate(self.evidence, 1)
        ]


def retrieve_evidence(
    question: str,
    retriever: Retriever,
    reranker: Reranker,
    *,
    threshold: float,
    candidates: int = 10,
    top_k: int = 3,
) -> GroundedAnswer:
    """Retrieve candidates, rerank them, and keep evidence only if it scores at least ``threshold``.

    If the best reranked chunk is below the threshold (or nothing matched at all), the answer is an
    abstention: no evidence is passed on, so a generator cannot answer from memory by accident.
    """
    ranked = rerank(question, retriever.search(question, candidates), reranker)
    if not ranked:
        return GroundedAnswer(question, True, (), "nothing in the corpus matched the question")
    if ranked[0].score < threshold:
        reason = f"best passage scored {ranked[0].score:.2f}, below the threshold {threshold:.2f}"
        return GroundedAnswer(question, True, (), reason)
    kept = tuple(hit for hit in ranked[:top_k] if hit.score >= threshold)
    return GroundedAnswer(question, False, kept, f"best passage scored {ranked[0].score:.2f}")


def build_prompt(answer: GroundedAnswer, *, strict: bool = False) -> str:
    """The instruction for a language model: answer from the numbered passages only, and cite.

    ``strict`` adds the rule that every sentence ends with a citation (see ``enforce_citations``).
    """
    if answer.abstained:
        return f"Reply exactly: {NO_ANSWER}"
    passages = "\n\n".join(f"[{n}] {h.chunk.text}" for n, h in enumerate(answer.evidence, 1))
    return (
        prompts.load("answer")
        .rstrip("\n")
        .format(
            strict=STRICT_CITATION_RULE if strict else "",
            no_answer=NO_ANSWER,
            passages=passages,
            question=answer.question,
        )
    )


def choose_threshold(answerable: Sequence[float], unanswerable: Sequence[float]) -> float:
    """The score cut-off that maximises balanced accuracy: the average of the share of answerable
    questions answered (score >= cut-off) and the share of unanswerable ones refused (score < it).

    Candidate cut-offs are midpoints between neighbouring observed scores; ties go to the higher.
    """
    scores = np.unique(np.concatenate([answerable, unanswerable]))
    candidates = [float(scores[0] - 1.0)]
    candidates += [float((a + b) / 2) for a, b in zip(scores[:-1], scores[1:], strict=True)]
    candidates.append(float(scores[-1] + 1.0))
    best, best_value = candidates[0], -1.0
    for cut in candidates:
        answered = np.mean(np.asarray(answerable) >= cut)
        refused = np.mean(np.asarray(unanswerable) < cut)
        value = float((answered + refused) / 2)
        if value >= best_value:
            best, best_value = cut, value
    return best


@dataclass(frozen=True)
class CitedReply:
    """A model reply after citation enforcement: the text to show, and what was removed."""

    text: str
    dropped: tuple[str, ...]  # sentences removed because they carried no valid citation
    invalid_markers: (
        int  # citation markers removed because they named a passage that does not exist
    )
    refused: bool


def split_sentences(text: str) -> list[str]:
    """Split a reply into sentences; a citation written after the full stop moves back before it.

    ``"X is true. [1] Y follows [2]."`` becomes ``["X is true [1].", "Y follows [2]."]``, so a
    citation placed after the punctuation still belongs to the sentence it follows.
    """
    text = _LIST_MARKER.sub(lambda m: m.group(1) + "\x00", text)  # protect list numbers
    text = _TRAILING_CITATION.sub(r" \2\1", text)
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\[])(?!\d{1,2}\x00)|\n+", text)
    parts = [p.strip().replace("\x00", ".") for p in pieces if p.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and _ONLY_CITATIONS.match(part):  # a citation alone on its own line
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def enforce_citations(reply: str, n_passages: int) -> CitedReply:
    """Keep only sentences that carry at least one citation to a passage that exists.

    Markers such as ``[7]`` when only 3 passages were given are removed, and a sentence left with no
    valid marker is dropped. If nothing is left the reply becomes the refusal. A refusal is returned
    unchanged. This guarantees every sentence shown has a citation; it does NOT check that the
    cited passage supports the sentence (that needs a person or a checker).
    """
    if reply.strip().lower().startswith("i don't know"):
        return CitedReply(reply.strip(), (), 0, True)
    kept: list[str] = []
    dropped: list[str] = []
    invalid = 0
    for sentence in split_sentences(reply):
        marks = [int(m) for m in _CITATION.findall(sentence)]
        bad = [m for m in marks if not 1 <= m <= n_passages]
        invalid += len(bad)
        if len(bad) == len(marks):  # no valid citation at all (or none given)
            dropped.append(sentence)
            continue
        kept.append(
            _CITATION.sub(
                lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_passages else "", sentence
            )
        )
    if not kept:
        return CitedReply(NO_ANSWER, tuple(dropped), invalid, True)
    return CitedReply(" ".join(kept), tuple(dropped), invalid, False)


ANSWERABILITY_PROMPT = prompts.load("answerability")


@dataclass(frozen=True)
class Answerability:
    """A language model's claim that the passages answer the question, checked by code."""

    label: str  # "full", "partial" or "none"
    quote: str  # the sentence the model says states the answer
    quote_found: bool  # that quote really appears (word for word) in one of the passages

    @property
    def can_answer(self) -> bool:
        """True only if the model says "full" AND its quote is really in the passages."""
        return self.label == "full" and self.quote_found


def answerability_prompt(question: str, evidence: Sequence[Hit]) -> str:
    passages = "\n\n".join(f"[{n}] {h.chunk.text}" for n, h in enumerate(evidence, 1))
    return ANSWERABILITY_PROMPT.format(question=question, passages=passages)


def _flat(text: str) -> str:
    return " ".join(re.sub(r"[#*_`>]", " ", text).split()).casefold()


def parse_answerability(
    raw: str, evidence: Sequence[Hit], min_quote_chars: int = 15
) -> Answerability:
    """Read the model's JSON reply and verify the quote against the passages.

    Anything unreadable counts as ``none``. The quote check ignores case, spacing and markdown.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return Answerability("none", "", False)
    if not isinstance(data, dict):  # valid JSON that is not an object, such as [] or "full"
        return Answerability("none", "", False)
    label = str(data.get("label", "none")).strip().lower()
    label = label if label in {"full", "partial", "none"} else "none"
    quote = str(data.get("quote") or "").strip().strip("\"'")
    flat = _flat(quote)
    found = len(flat) >= min_quote_chars and any(flat in _flat(h.chunk.text) for h in evidence)
    return Answerability(label, quote, found)
