"""What the assistant says when a guard blocks something, and what is recorded.

The replies are fixed text. They never say which rule fired or quote the input: telling an attacker
"your message matched the pattern X" is a tuning guide. The reason code goes to the response's
``reason`` field (``guardrail:<code>``) and the log, which only the operator and the caller's own
client see; it names a rule, never the content.
"""

from __future__ import annotations

REASON_PREFIX = "guardrail:"

# Shown when the question itself was blocked (an attack, or nothing to answer).
INPUT_BLOCKED = (
    "I can't help with that request. Ask a question about payments and I will answer from the "
    "documents."
)
# Shown when the question was fine but the drafted answer failed a check.
OUTPUT_BLOCKED = (
    "I couldn't produce a reliable answer from the documents. Please rephrase the question or "
    "ask something else."
)


def reason(*codes: str) -> str:
    return REASON_PREFIX + ",".join(codes)
