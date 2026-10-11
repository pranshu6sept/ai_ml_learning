"""The input guard: what happens to a question before the pipeline sees it.

    verdict = check_input(question, shield=azure_prompt_shield)   # shield is optional

In order:

1. **Normalise** the text (compatibility forms folded, invisible characters removed), drop control
   characters, so a disguised instruction is read the way the model would read it.
2. **Length**: empty or over the limit is blocked.
3. **PII**: card numbers, IBANs and account numbers are *redacted*, not blocked. The question goes
   without them, so the model, the search service and the logs never see the number.
4. **Injection patterns**: a short list of regular expressions for the best-known override and
   prompt-extraction phrasings. Cheap and local; it catches the textbook attacks and nothing subtle.
5. **Shield**: an optional function (Azure AI Content Safety Prompt Shields), True when it
   detects an attack. It runs last, on the redacted text, so no card number is sent to it either.

A blocked question gets a fixed reply (see ``policy``) and a reason code; the reason is for logs and
reports, and the reply never explains which rule fired, so an attacker cannot tune around it.

Limits: the patterns are English-only and literal. A paraphrase, a translation, a split
instruction or a role-play framing passes them; the shield and the output guard exist for what
the patterns miss.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from .pii import normalize, redact

MAX_CHARS = 1000

INJECTION = "injection_pattern"
SHIELD = "prompt_shield"
EMPTY = "empty"
TOO_LONG = "too_long"
PII_REDACTED = "pii_redacted"  # informational: the question was allowed, with numbers removed

Shield = Callable[[str], bool]  # True when the text looks like an attack

_PATTERNS = [
    # Overriding the instructions.
    r"\b(?:ignore|disregard|forget|override|bypass)\b.{0,40}\b(?:previous|prior|above|earlier|preceding|all|any|your|these)\b"
    r".{0,30}\b(?:instructions?|prompts?|rules?|guidelines?|directives?|restrictions?)\b",
    r"\bforget\s+(?:everything|all)\b.{0,30}\b(?:you|your|told|know)\b",
    # Extracting the hidden prompt.
    r"\b(?:reveal|show|print|repeat|output|display|tell me|leak|dump)\b.{0,50}"
    r"\b(?:system|hidden|initial|original|secret)\s+(?:prompt|instructions?|message)\b",
    r"\bwhat\s+(?:is|are|were)\s+your\s+(?:system\s+)?(?:instructions?|prompt|rules)\b",
    # Switching persona or mode.
    r"\byou\s+are\s+now\b.{0,40}"
    r"\b(?:dan|unrestricted|unfiltered|jailbroken|developer mode|no restrictions)\b",
    r"\b(?:developer|debug|god|admin)\s+mode\b",
    r"\bdo\s+anything\s+now\b",
    r"\bjailbreak(?:ed|ing)?\b",
    r"\b(?:pretend|act|behave)\b.{0,30}"
    r"\b(?:no|without|free of)\s+(?:restrictions?|rules?|filters?|limits?|guidelines?)\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PATTERNS]


@dataclass(frozen=True)
class InputVerdict:
    allowed: bool
    text: str  # the question to use: normalised and redacted (the original is not kept)
    reasons: tuple[str, ...]  # why it was blocked, or PII_REDACTED when it was cleaned
    redactions: tuple[str, ...] = ()  # kinds of identifier removed


def _strip_controls(text: str) -> str:
    return "".join(
        ch for ch in text if ch in "\n\t " or not unicodedata.category(ch).startswith("C")
    )


def injection_patterns_match(text: str) -> bool:
    return any(p.search(text) for p in _COMPILED)


def check_input(
    question: str, *, shield: Shield | None = None, max_chars: int = MAX_CHARS
) -> InputVerdict:
    text = " ".join(_strip_controls(normalize(question)).split())
    if not text:
        return InputVerdict(False, "", (EMPTY,))
    if len(text) > max_chars:
        return InputVerdict(False, "", (TOO_LONG,))
    redaction = redact(text)
    cleaned = redaction.text
    kinds = tuple(dict.fromkeys(f.kind for f in redaction.findings))
    notes = (PII_REDACTED,) if kinds else ()
    if injection_patterns_match(cleaned):
        return InputVerdict(False, "", (INJECTION,), kinds)
    if shield is not None and shield(cleaned):
        return InputVerdict(False, "", (SHIELD,), kinds)
    return InputVerdict(True, cleaned, notes, kinds)
