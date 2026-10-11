"""The output guard: what happens to an answer before the caller sees it.

    verdict = check_output(reply, passages, refused=False, secrets=prompt_texts)

In order:

1. **Shape** (Pydantic): the reply is non-empty and not absurdly long.
2. **Citations**: an answer (not a refusal) must cite at least one passage, and every marker must
   point at a passage that exists.
3. **System-prompt leakage** (OWASP LLM07): a block of at least ``LEAK_CHARS`` characters copied
   from one of the supplied secret texts (the prompt templates) means the model is reciting its
   instructions; the answer is blocked.
4. **Support**: every sentence must share enough content words with the passage it cites (see
   ``support``). This is what stops an injected, validly cited instruction such as
   ``HACKED [1]``.
5. **PII** (OWASP LLM02): identifiers in the answer are redacted. This runs last so the earlier
   checks see the real text.

A blocked answer is replaced by a fixed fallback (see ``policy``); redaction alone does not block.

Limits: leakage detection is verbatim only (a paraphrased or translated prompt passes); the
support check is lexical (see its module for what it cannot catch); PII detection covers three
identifier kinds.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from .pii import redact
from .support import DEFAULT_THRESHOLD, answer_support

LEAK_CHARS = 40
MAX_REPLY_CHARS = 4000

BAD_SHAPE = "bad_shape"
NO_CITATION = "no_citation"
BAD_CITATION = "bad_citation"
PROMPT_LEAK = "prompt_leak"
UNSUPPORTED = "unsupported_sentence"
PII_REDACTED = "pii_redacted"  # informational: the answer was allowed, with numbers removed

_CITATION = re.compile(r"\[(\d+)\]")


class Reply(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_REPLY_CHARS)


@dataclass(frozen=True)
class OutputVerdict:
    allowed: bool
    text: str  # the text to show when allowed (PII redacted); empty when blocked
    reasons: tuple[str, ...]
    redactions: tuple[str, ...] = ()
    support_min: float | None = None  # the weakest sentence's lexical support (None for refusals)


def _squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def leaks_secret(reply: str, secrets: Sequence[str], chars: int = LEAK_CHARS) -> bool:
    """True if ``chars`` or more consecutive characters of any secret appear in ``reply``."""
    haystack = _squash(reply)
    for secret in secrets:
        needle = _squash(secret)
        for start in range(0, max(1, len(needle) - chars + 1), max(1, chars // 2)):
            window = needle[start : start + chars]
            if len(window) == chars and window in haystack:
                return True
    return False


def check_output(
    reply: str,
    passages: Sequence[str],
    *,
    refused: bool,
    secrets: Sequence[str] = (),
    threshold: float = DEFAULT_THRESHOLD,
) -> OutputVerdict:
    try:
        Reply(text=reply)
    except ValidationError:
        return OutputVerdict(False, "", (BAD_SHAPE,))
    if leaks_secret(reply, secrets):
        return OutputVerdict(False, "", (PROMPT_LEAK,))
    if not refused:
        marks = [int(n) for n in _CITATION.findall(reply)]
        if not marks:
            return OutputVerdict(False, "", (NO_CITATION,))
        if any(not 1 <= n <= len(passages) for n in marks):
            return OutputVerdict(False, "", (BAD_CITATION,))
        scores = answer_support(reply, passages)
        weakest = min((s.support for s in scores), default=1.0)
        if weakest < threshold:
            return OutputVerdict(False, "", (UNSUPPORTED,), (), weakest)
        support_min: float | None = weakest
    else:
        support_min = None
    redaction = redact(reply)
    kinds = tuple(dict.fromkeys(f.kind for f in redaction.findings))
    return OutputVerdict(True, redaction.text, (PII_REDACTED,) if kinds else (), kinds, support_min)
