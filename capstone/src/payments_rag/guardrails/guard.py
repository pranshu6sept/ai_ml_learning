"""Put the input and output guards around an answering function.

    safe = guarded(answerer, shield=prompt_shield)
    answer = safe("What is ISO 20022?")

``answerer`` is any ``question -> Answer`` function (the Azure pipeline in production, a fake in
tests). The wrapper:

* checks the question first; a blocked question never reaches the pipeline (no search, no model);
* passes the *redacted* question on, and puts it in the returned ``Answer``, so a
  card number is not echoed back to the caller or kept in the response;
* checks the drafted answer against the passages it came from; a failing answer is replaced by
  the fixed fallback and marked refused with the reason code;
* sends the reasons to ``on_event`` (the log) without the question or the answer text.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from .. import prompts, telemetry
from ..ask import Answer
from . import policy
from .input import Shield, check_input
from .output import check_output

Answerer = Callable[[str], Answer]
EventSink = Callable[[str, tuple[str, ...]], None]  # (stage, reason codes)


PLATFORM_FILTER = "platform_filter"


def platform_filtered(error: BaseException) -> bool:
    """True for the Azure OpenAI error raised when its content filter refuses a prompt.

    Recognised by its ``code`` attribute (``openai.BadRequestError`` carries it), so this module
    does not need the ``openai`` package.
    """
    return getattr(error, "code", None) == "content_filter"


def prompt_secrets() -> list[str]:
    """The prompt templates: text that must never come back in an answer."""
    return [prompts.load(name) for name in prompts.prompt_names()]


def guarded(
    answerer: Answerer,
    *,
    shield: Shield | None = None,
    secrets: Sequence[str] | None = None,
    on_event: EventSink | None = None,
) -> Answerer:
    hidden = list(prompt_secrets() if secrets is None else secrets)

    def emit(stage: str, codes: tuple[str, ...]) -> None:
        if on_event is not None and codes:
            on_event(stage, codes)

    def answer(question: str) -> Answer:
        with telemetry.span("guard.input") as stage:
            verdict = check_input(question, shield=shield)
            stage.set_attribute("payrag.guard_blocked", not verdict.allowed)
            stage.set_attribute("payrag.guard_reasons", ",".join(verdict.reasons))
            stage.set_attribute("payrag.pii_redactions", ",".join(verdict.redactions))
        emit("input", verdict.reasons)
        if not verdict.allowed:
            telemetry.request_attribute("payrag.guard_stage", "input")
            telemetry.request_attribute("payrag.guard_reason", ",".join(verdict.reasons))
            return Answer("", policy.INPUT_BLOCKED, (), True, policy.reason(*verdict.reasons))

        try:
            result = answerer(verdict.text)
        except Exception as error:
            if not platform_filtered(error):
                raise
            # The Azure OpenAI deployment's own content filter refused the prompt (HTTP 400,
            # code "content_filter"): a refusal, not a server error.
            emit("pipeline", (PLATFORM_FILTER,))
            telemetry.request_attribute("payrag.guard_stage", "pipeline")
            telemetry.request_attribute("payrag.guard_reason", PLATFORM_FILTER)
            return Answer(
                verdict.text, policy.INPUT_BLOCKED, (), True, policy.reason(PLATFORM_FILTER)
            )
        passages = [hit.chunk.text for hit in result.evidence]
        with telemetry.span("guard.output") as stage:
            out = check_output(result.text, passages, refused=result.refused, secrets=hidden)
            stage.set_attribute("payrag.guard_blocked", not out.allowed)
            stage.set_attribute("payrag.guard_reasons", ",".join(out.reasons))
            if out.support_min is not None:
                stage.set_attribute("payrag.support_min", out.support_min)
        emit("output", out.reasons)
        telemetry.request_attribute("payrag.support_min", out.support_min)
        if not out.allowed:
            telemetry.request_attribute("payrag.guard_stage", "output")
            telemetry.request_attribute("payrag.guard_reason", ",".join(out.reasons))
            return Answer(
                verdict.text, policy.OUTPUT_BLOCKED, (), True, policy.reason(*out.reasons)
            )
        text = out.text
        # A refusal keeps the pipeline's own reason; a guard-cleaned answer gets the note appended.
        note = (
            policy.reason(*verdict.reasons, *out.reasons)
            if (verdict.reasons or out.reasons)
            else ""
        )
        reason = f"{result.reason}; {note}" if note and result.reason else (note or result.reason)
        return replace(result, question=verdict.text, text=text, reason=reason)

    return answer
