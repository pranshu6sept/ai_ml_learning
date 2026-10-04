# ruff: noqa: E501
"""Judge prompts and parsers for answer quality: faithfulness, relevance and correctness.

Three questions about an answer, each asked of a language model that returns JSON:

* **faithfulness** (groundedness): the judge splits the answer into claims and marks each as
  supported or not by the passages the answer was written from. Score = supported / total claims.
* **relevance**: does the answer address the question that was asked (``direct`` 1.0, ``partial``
  0.5, ``off_topic`` 0), whether or not it is true?
* **correctness**: compared with the reference answer written from the gold passage (``correct``
  1.0, ``partial`` 0.5, ``incorrect`` 0).

The parsers never trust the model's shape: anything that is not the expected JSON gives ``None``
(counted as "judge failed" by the runner), never a made-up score. Caveat the runner repeats: when
the judge is the same model that wrote the answer, its verdicts are optimistic and imperfect.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from .retrieval import Hit

RELEVANCE_SCORES = {"direct": 1.0, "partial": 0.5, "off_topic": 0.0}
CORRECTNESS_SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}

_FAITHFULNESS = """You check an answer against the numbered passages it was written from.
Split the answer into its separate factual claims (ignore citation markers like [1]). For each claim, say whether the passages state it or directly imply it. Do not use outside knowledge: a true claim that the passages do not support is NOT supported.
Return only JSON: {"claims": [{"claim": "<short claim>", "supported": true}]}

Passages:
<<PASSAGES>>

Answer:
<<ANSWER>>"""

_RELEVANCE = """Does the answer address the question that was asked? Judge only whether it is on point, not whether it is true.
- direct: it answers the question asked.
- partial: it answers only part of the question, or something close to it.
- off_topic: it does not answer the question (including "I don't know").
Return only JSON: {"verdict": "direct"}, {"verdict": "partial"} or {"verdict": "off_topic"}.

Question: <<QUESTION>>

Answer:
<<ANSWER>>"""

_CORRECTNESS = """Compare an answer with the reference answer for the same question. Judge the facts, not the wording.
- correct: the answer gives the key facts of the reference and nothing that contradicts it. Extra detail that does not contradict the reference is fine.
- partial: it gives some but not all of the reference's key facts, or contains a claim that contradicts the reference.
- incorrect: it misses the key facts, contradicts the reference, or refuses to answer.
Return only JSON: {"verdict": "correct"}, {"verdict": "partial"} or {"verdict": "incorrect"}.

Question: <<QUESTION>>

Reference answer:
<<REFERENCE>>

Answer to judge:
<<ANSWER>>"""


def _passages(evidence: Sequence[Hit]) -> str:
    return "\n\n".join(f"[{n}] {h.chunk.text}" for n, h in enumerate(evidence, 1))


def faithfulness_prompt(answer: str, evidence: Sequence[Hit]) -> str:
    return _FAITHFULNESS.replace("<<PASSAGES>>", _passages(evidence)).replace("<<ANSWER>>", answer)


def relevance_prompt(question: str, answer: str) -> str:
    return _RELEVANCE.replace("<<QUESTION>>", question).replace("<<ANSWER>>", answer)


def correctness_prompt(question: str, reference: str, answer: str) -> str:
    return (
        _CORRECTNESS.replace("<<QUESTION>>", question)
        .replace("<<REFERENCE>>", reference)
        .replace("<<ANSWER>>", answer)
    )


@dataclass(frozen=True)
class Faithfulness:
    supported: int
    total: int
    unsupported: tuple[str, ...]

    @property
    def score(self) -> float:
        """Share of claims supported; ``nan`` when the judge found no claims at all."""
        return self.supported / self.total if self.total else float("nan")


def _load(raw: str) -> dict[str, object] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def parse_faithfulness(raw: str) -> Faithfulness | None:
    data = _load(raw)
    claims = data.get("claims") if data else None
    if not isinstance(claims, list):
        return None
    supported = 0
    unsupported: list[str] = []
    for item in claims:
        if not isinstance(item, dict) or not isinstance(item.get("supported"), bool):
            return None
        if item["supported"]:
            supported += 1
        else:
            unsupported.append(str(item.get("claim", "")))
    return Faithfulness(supported, len(claims), tuple(unsupported))


def parse_verdict(raw: str, scores: dict[str, float]) -> tuple[str, float] | None:
    """The verdict word and its score, or ``None`` if it is not one of the allowed verdicts."""
    data = _load(raw)
    verdict = data.get("verdict") if data else None
    if not isinstance(verdict, str) or verdict not in scores:
        return None
    return verdict, scores[verdict]


def agreement(first: Sequence[str], second: Sequence[str]) -> tuple[float, float]:
    """How often two judges give the same label: (raw agreement, Cohen's kappa).

    Raw agreement is the share of items with the same label. Kappa corrects it for the agreement two
    judges would reach by chance given how often each uses each label: 1 is perfect, 0 is no better
    than chance. When chance agreement is already 1 (both judges use one label for everything)
    kappa is undefined and returned as ``nan``; read the raw agreement then.
    """
    if len(first) != len(second):
        raise ValueError("both judges must label the same items")
    if not first:
        return float("nan"), float("nan")
    n = len(first)
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / n
    chance = sum(
        (first.count(label) / n) * (second.count(label) / n) for label in set(first) | set(second)
    )
    kappa = (observed - chance) / (1 - chance) if chance < 1 else float("nan")
    return observed, kappa
