"""A lexical check that each sentence of an answer is backed by the passages it cites.

``enforce_citations`` only checks that a sentence *carries* a citation to a passage that exists.
An injected instruction that asks for ``HACKED [1]`` satisfies that, as the Week 7 injection probe
showed. This check asks the next question: do the sentence's content words appear in the passage
it cites?

    support(sentence) = share of the sentence's content words (stop words removed, stemmed)
                        that also occur in the cited passages

A sentence below the threshold is *unsupported*. If it cites nothing valid, all passages count.

What this is and is not. It is cheap, local and deterministic, and it catches an answer that says
something the passages never mention. It is **not** a faithfulness judge: a sentence made only of
words from the passage can still be false ("the window is 12 days" when the passage says 120), and
a correct paraphrase that uses different words can score low. It is a floor under the model-based
checks, not a replacement for them.

Threshold. Measured on the 52 answers the pipeline gave in the Week 5 no-ranker run
(results/generation_no_semantic.json): the median answer's weakest sentence scores 0.86 and the
lowest faithful answer 0.29. At 0.5 the check would block 2 of 52 faithful answers (good
paraphrases); at 0.3, 1; at 0.25, none. It does not separate the two answers the Week 5 judge found
not fully faithful (0.60 and 0.62) from faithful ones. 0.25 was chosen on this same data, so zero
false blocks is optimistic; the check is meant for gross failures, where the answer's words are
not in the passages at all.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ..grounding import split_sentences
from ..retrieval import make_analyzer

_CITATION = re.compile(r"\[(\d+)\]")
_stem_and_filter = make_analyzer(stem=True)
# Words an answer may use without the passage containing them ("Yes, ..." answers yes/no questions).
_NEUTRAL = frozenset({"yes"})


def _analyze(text: str) -> list[str]:
    return [t for t in _stem_and_filter(text) if t not in _NEUTRAL]


DEFAULT_THRESHOLD = 0.25


@dataclass(frozen=True)
class SentenceSupport:
    sentence: str
    support: float  # 0..1; 1.0 when the sentence has no content words to check
    cited: tuple[int, ...]  # valid passage numbers the sentence cites (empty: all passages checked)
    missing: tuple[str, ...]  # content words not found in the passages


def sentence_support(sentence: str, passages: Sequence[str]) -> SentenceSupport:
    """Support of one sentence against the passages it cites (all of them if none is valid)."""
    cited = tuple(
        sorted({int(n) for n in _CITATION.findall(sentence) if 1 <= int(n) <= len(passages)})
    )
    pool = " ".join(passages[n - 1] for n in cited) if cited else " ".join(passages)
    pool_terms = set(_analyze(pool))
    terms = _analyze(_CITATION.sub(" ", sentence))
    if not terms:
        return SentenceSupport(sentence, 1.0, cited, ())
    missing = tuple(dict.fromkeys(t for t in terms if t not in pool_terms))
    covered = sum(1 for t in terms if t in pool_terms)
    return SentenceSupport(sentence, covered / len(terms), cited, missing)


def answer_support(reply: str, passages: Sequence[str]) -> list[SentenceSupport]:
    """Support of every sentence of ``reply``."""
    return [sentence_support(s, passages) for s in split_sentences(reply)]


def unsupported(
    reply: str, passages: Sequence[str], threshold: float = DEFAULT_THRESHOLD
) -> list[SentenceSupport]:
    """The sentences whose support is below ``threshold``."""
    return [s for s in answer_support(reply, passages) if s.support < threshold]
