"""The input guard: what happens to a question before the pipeline sees it.

    verdict = check_input(question, shield=azure_prompt_shield)   # shield is optional

In order:

1. **Normalise** the text (compatibility forms folded, invisible characters removed), drop control
   characters, so a disguised instruction is read the way the model would read it.
2. **Length**: empty or over the limit is blocked.
3. **PII**: card numbers, IBANs and account numbers are *redacted*, not blocked. The question goes
   on without them, so the model, the search service and the logs never see the number.
4. **Injection patterns**: regular expressions for the best-known override, prompt-extraction and
   persona-switch phrasings, tested on the text and on decoded forms of it (look-alike letters
   folded, spaced-out letters joined, leetspeak undone, reversed, base64 decoded). Cheap and
   local; it catches known phrasings and nothing subtle.
5. **Shield**: an optional function (Azure AI Content Safety Prompt Shields), True when it detects
   an attack. It runs last, on the redacted text, so no card number is sent to it either.

A blocked question gets a fixed reply (see ``policy``) and a reason code; the reason is for logs and
reports, and the reply never explains which rule fired, so an attacker cannot tune around it.

Limits: the patterns are English-only and literal. A paraphrase, a translation, a split instruction
or a role-play framing passes them, and so does a harmful request that uses no injection phrasing at
all ("write a story about moving stolen money"); the shield, the pipeline's own refusal and the
output guard exist for what the patterns miss. The words they match were chosen after seeing which
legitimate payments questions use them ("bypass 3-D Secure rules", "developer mode in a sandbox").
"""

from __future__ import annotations

import base64
import binascii
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

_OVERRIDE = r"(?:ignore|disregard|forget|override|bypass|disable)"
_PATTERNS = [
    # Overriding the instructions: "ignore all previous instructions".
    rf"\b{_OVERRIDE}\b.{{0,40}}\b(?:previous|prior|above|earlier|preceding|all|any|your|these)\b"
    r".{0,30}\b(?:instructions?|prompts?|directives?)\b",
    # ... the same with the noun first: "disregard the rules above".
    rf"\b{_OVERRIDE}\b.{{0,40}}\b(?:instructions?|prompts?|rules?|guidelines?|directives?)\b"
    r".{0,25}\b(?:above|before|earlier|previously|prior)\b",
    # ... and for rules only with an attack-specific qualifier (bypassing 3-D Secure rules is fine).
    rf"\b{_OVERRIDE}\b.{{0,40}}\b(?:previous|prior|above|earlier|preceding|your|these|safety|system)\b"
    r".{0,30}\b(?:rules?|guidelines?|restrictions?|filters?|guardrails?|policies)\b",
    r"\bforget\s+(?:everything|all)\b.{0,30}\b(?:you|your|told|know)\b",
    r"\binstructions?\s+(?:above|before)\s+(?:are|were)\s+(?:outdated|obsolete|wrong|void)\b",
    r"\b(?:follow|obey)\s+(?:these|the following)\s+(?:instead|instructions?)\b",
    r"\boverrides?\s+your\s+(?:configuration|instructions|settings|programming)\b",
    # Extracting the hidden prompt.
    r"\b(?:reveal|show|print|repeat|output|display|tell me|leak|dump|give me|copy|translate|"
    r"summari[sz]e|paraphrase|list)\b.{0,50}\byour\s+(?:(?:system|hidden|initial|original|secret)\s+)?"
    r"(?:prompt|instructions?|configuration|guidelines|system message|rules)\b",
    r"\b(?:reveal|show|print|repeat|output|display|tell me|leak|dump)\b.{0,50}"
    r"\b(?:system|hidden|initial|original|secret)\s+(?:prompt|instructions?|message)\b",
    r"\bwhat\s+(?:is|are|were)\s+your\s+(?:system\s+)?(?:instructions?|prompt|rules)\b",
    r"\bwhat\s+(?:were|was)\s+you\s+(?:told|given|instructed)\b",
    r"\b(?:rules|instructions|guidelines)\s+(?:that\s+)?you\s+(?:follow|were given|are given|use|"
    r"have been given|must follow)\b",
    r"\brepeat\b.{0,25}\b(?:words|text|everything|lines|message)\s+(?:above|before)\b",
    r"\b(?:template|prompt)\s+you\s+use\b",
    r"\bverbatim\b.{0,40}\byou\s+were\s+given\b",
    # Switching persona or mode.
    r"\byou\s+are\s+(?:now\s+)?(?:a\s+different\s+(?:assistant|ai|bot)|dan)\b",
    r"\byou\s+are\s+now\b.{0,40}"
    r"\b(?:dan|unrestricted|unfiltered|jailbroken|developer mode|no restrictions)\b",
    r"\b(?:enable|activate|enter|switch\s+to|turn\s+on)\s+(?:developer|debug|god|admin)\s+mode\b",
    r"\b(?:developer|god)\s+mode\b.{0,40}\b(?:without|no)\s+(?:any\s+)?(?:filters?|restrictions?|rules?)\b",
    r"\bdo\s+anything\s+now\b",
    r"\bjailbreak(?:ed|ing)?\b",
    r"\bopposite\s+day\b",
    r"\b(?:unfiltered|uncensored|unrestricted)\s+(?:one|version|assistant|ai|mode)\b",
    r"\b(?:pretend|act|behave)\b.{0,30}"
    r"\b(?:no|without|free of)\s+(?:restrictions?|rules?|filters?|limits?|guidelines?)\b",
    # Fake role markers: "###SYSTEM###", "[SYSTEM]", "<system>".
    r"(?:#{3}|\[|<)\s*system\s*(?:#{3}|\]|>)",
]
_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _PATTERNS]

# Letters from other alphabets that look like Latin ones.
_CONFUSABLES = str.maketrans(
    "аеорсухіјѕһԁԛԝοαειυνρτκ",  # Cyrillic and Greek look-alikes
    "aeopcyxijshdqwoaeiuvptk",
)
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_SPACED = re.compile(r"(?:(?<=\s)|^)(?:\w ){2,}\w(?=\s|$)")
_BASE64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


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


def _decoded_base64(text: str) -> list[str]:
    found = []
    for token in _BASE64.findall(text):
        try:
            raw = base64.b64decode(token + "=" * (-len(token) % 4), validate=True)
            decoded = raw.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if decoded and sum(c.isprintable() for c in decoded) / len(decoded) > 0.9:
            found.append(decoded)
    return found


def variants(text: str) -> list[str]:
    """The text and the forms an attacker may have hidden it in, for pattern matching only."""
    folded = text.translate(_CONFUSABLES)
    spaced = _SPACED.sub(lambda m: m.group().replace(" ", ""), folded)
    collapsed = " ".join(folded.split())
    forms = [collapsed, " ".join(spaced.split()), collapsed.translate(_LEET), collapsed[::-1]]
    forms += _decoded_base64(collapsed)
    return list(dict.fromkeys(forms))


def injection_patterns_match(text: str) -> bool:
    return any(p.search(form) for form in variants(text) for p in _COMPILED)


def check_input(
    question: str, *, shield: Shield | None = None, max_chars: int = MAX_CHARS
) -> InputVerdict:
    raw = _strip_controls(normalize(question))
    text = " ".join(raw.split())
    if not text:
        return InputVerdict(False, "", (EMPTY,))
    if len(text) > max_chars:
        return InputVerdict(False, "", (TOO_LONG,))
    redaction = redact(text)
    cleaned = redaction.text
    kinds = tuple(dict.fromkeys(f.kind for f in redaction.findings))
    notes = (PII_REDACTED,) if kinds else ()
    # Spaced-out letters show only before whitespace is collapsed, so match the raw form too.
    if injection_patterns_match(cleaned) or injection_patterns_match(redact(raw).text):
        return InputVerdict(False, "", (INJECTION,), kinds)
    if shield is not None and shield(cleaned):
        return InputVerdict(False, "", (SHIELD,), kinds)
    return InputVerdict(True, cleaned, notes, kinds)
