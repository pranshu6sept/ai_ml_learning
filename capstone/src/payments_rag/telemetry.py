"""Telemetry: OpenTelemetry spans and per-request totals, sent to Application Insights.

    with span("retrieval.search", top_k=3) as s:
        ...
        s.set_attribute("payrag.hits", 3)

Everything here is a **no-op when OpenTelemetry is not installed or not configured**, so the
library and its tests run without it. ``setup()`` turns it on: it needs the
``azure-monitor-opentelemetry`` package (in the API image's requirements) and an Application
Insights connection string, and it signs in to Application Insights with the app's own identity
(no key), which needs the "Monitoring Metrics Publisher" role on the component.

What a request records (all on spans, queryable in Application Insights):

* one **request** span for ``POST /ask`` (from the FastAPI instrumentation) carrying the totals:
  ``payrag.tokens_in``, ``payrag.tokens_out``, ``payrag.cost_usd`` (an *estimate*, see ``PRICES``),
  ``payrag.refused``, ``payrag.reason_code`` and ``payrag.support_min`` (see below);
* a **span per model call** (``llm.chat``, ``embedding``) with latency, ``gen_ai.usage.*`` token
  counts and the deployment name;
* a **retrieval span** with the number of hits, their document ids and the best score;
* the **guard stages** (``guard.input``, ``guard.output``) with their outcome.

Cost is tokens times a per-million-token price kept in ``PRICES``. Those prices are list prices
written down here, not read from the bill; treat the dashboard's cost as an estimate and compare it
with Cost Management. Override them with ``PAYRAG_PRICES`` (JSON) if they change.

``payrag.support_min`` is the weakest sentence's lexical support (see ``guardrails.support``). It
is a cheap online *proxy* for how well an answer is grounded, not a groundedness score from a
model.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

_trace: Any  # the opentelemetry.trace module, or None when OpenTelemetry is not installed
try:  # the API is small; the exporter and SDK are only needed in the deployed image
    from opentelemetry import trace as _trace_module

    _trace = _trace_module
except ImportError:  # pragma: no cover - exercised when the package is absent
    _trace = None

log = logging.getLogger("payments_rag.telemetry")

# US dollars per million tokens: (input, output). List prices written down by hand on 2026-10-12
# and NOT verified against the invoice: an estimate. Override with the PAYRAG_PRICES environment
# variable, for example {"gpt-4.1-mini": [0.4, 1.6]}.
PRICES: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "text-embedding-3-small": (0.02, 0.0),
}


class _NoSpan:
    """Stands in for a span when OpenTelemetry is not installed."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass


@dataclass
class RequestTotals:
    """Usage added up over one request (one ``POST /ask``)."""

    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model_calls: int = 0


_totals: contextvars.ContextVar[RequestTotals | None] = contextvars.ContextVar(
    "payrag_totals", default=None
)
_request_span: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "payrag_request_span", default=None
)


def prices() -> dict[str, tuple[float, float]]:
    """The price table, with ``PAYRAG_PRICES`` applied on top."""
    table = dict(PRICES)
    raw = os.environ.get("PAYRAG_PRICES", "").strip()
    if raw:
        try:
            table |= {k: (float(v[0]), float(v[1])) for k, v in json.loads(raw).items()}
        except (ValueError, TypeError, KeyError, IndexError):
            log.warning("PAYRAG_PRICES is not valid; using the built-in prices")
    return table


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimated US dollars for one call; 0 for a model with no listed price."""
    price_in, price_out = prices().get(model, (0.0, 0.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """A child span of the current one (a no-op object when OpenTelemetry is absent)."""
    if _trace is None:
        yield _NoSpan()
        return
    with _trace.get_tracer("payments_rag").start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current


def current_span() -> Any:
    return _trace.get_current_span() if _trace is not None else _NoSpan()


def current_trace_id() -> str | None:
    """The trace id (32 hex characters) of the current span, or None outside a trace."""
    if _trace is None:
        return None
    context = _trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


def begin_request() -> RequestTotals:
    """Start adding up usage for one request; call at the top of the request handler.

    Also remembers the request's span, so code deeper in the pipeline (the guards) can put a fact on
    it with ``request_attribute`` even from inside a child span.
    """
    totals = RequestTotals()
    _totals.set(totals)
    _request_span.set(current_span())
    return totals


def request_attribute(key: str, value: Any) -> None:
    """Set an attribute on the request span started by ``begin_request`` (no-op if none)."""
    target = _request_span.get()
    if target is not None and value is not None:
        target.set_attribute(key, value)


def record_model_call(model: str, tokens_in: int, tokens_out: int, span_: Any = None) -> float:
    """Add one model call to the request's totals and to ``span_``; returns its estimated cost."""
    cost = estimate_cost(model, tokens_in, tokens_out)
    totals = _totals.get()
    if totals is not None:
        totals.tokens_in += tokens_in
        totals.tokens_out += tokens_out
        totals.cost_usd += cost
        totals.model_calls += 1
    if span_ is not None:
        span_.set_attribute("gen_ai.usage.input_tokens", tokens_in)
        span_.set_attribute("gen_ai.usage.output_tokens", tokens_out)
        span_.set_attribute("payrag.cost_usd", cost)
    return cost


def annotate_request(totals: RequestTotals, **attributes: Any) -> None:
    """Put the request's totals (and any extra attributes) on the current span."""
    current = current_span()
    current.set_attribute("payrag.tokens_in", totals.tokens_in)
    current.set_attribute("payrag.tokens_out", totals.tokens_out)
    current.set_attribute("payrag.cost_usd", round(totals.cost_usd, 6))
    current.set_attribute("payrag.model_calls", totals.model_calls)
    for key, value in attributes.items():
        if value is not None:
            current.set_attribute(key, value)


def setup(connection_string: str | None = None, credential: Any = None) -> bool:
    """Send telemetry to Application Insights. Returns True if it was switched on.

    Reads ``APPLICATIONINSIGHTS_CONNECTION_STRING`` when no string is given. With no string, or if
    the distro is not installed, nothing happens and the app runs without telemetry. The credential
    defaults to the app's managed identity (``DefaultAzureCredential`` also works locally after
    ``az login``); local (key) authentication is disabled on the component, so there is no key.
    """
    connection_string = connection_string or os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        log.warning("telemetry is configured but azure-monitor-opentelemetry is not installed")
        return False
    if credential is None:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
    configure_azure_monitor(connection_string=connection_string, credential=credential)
    # Python loggers default to WARNING, which silently drops this package's INFO records (the
    # feedback event, the guard events). Without this only warnings reached Application Insights.
    logging.getLogger("payments_rag").setLevel(logging.INFO)
    return True
