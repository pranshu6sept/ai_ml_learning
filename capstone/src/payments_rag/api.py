"""The capstone as a web service: `/health`, `POST /ask`, `POST /feedback`.

    uv run --group api uvicorn payments_rag.api:app     # needs `az login` and the .env settings

The app is built by `create_app(answerer=...)` from an injected function, so the HTTP layer is
tested without Azure. In production the answerer is the pipeline behind
`python -m payments_rag.ask`:
hybrid search with the semantic ranker, a quote-verified answerability check, then a cited answer
or a refusal.

Because this sits in front of a paid model on a public URL, three guards run before any model call:
* the question must be 1 to 1000 characters (a long prompt costs tokens);
* a global rate limit (default 30 requests a minute for the whole process) caps spend from a flood;
* if `PAYRAG_API_KEY` is set, requests must send it in the `X-API-Key` header (constant-time check).
The rate limit is per process: with several instances the real limit is that many times larger.

Azure access is keyless (`DefaultAzureCredential`): `az login` locally, the managed identity
when hosted.
"""

from __future__ import annotations

import hmac
import logging
import os
import threading
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .ask import Answer

log = logging.getLogger("payments_rag.api")

MAX_QUESTION_CHARS = 1000
DEFAULT_RATE_PER_MINUTE = 30
MAX_FEEDBACK_ITEMS = 1000

# The page may load only its own scripts, styles and connections and may not be framed. /docs and
# /redoc load their interface from a CDN, so they are left out of the CSP (other headers apply).
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
NO_CSP_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect"}

Answerer = Callable[[str], Answer]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)


class AskResponse(BaseModel):
    request_id: str
    question: str
    answer: str
    sources: list[str]
    refused: bool
    reason: str
    latency_ms: int


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=64)
    rating: Literal["up", "down"]
    comment: str = Field(default="", max_length=1000)


class FeedbackResponse(BaseModel):
    stored: bool


class HealthResponse(BaseModel):
    status: Literal["ok"]
    configured: bool


@dataclass
class RateLimiter:
    """At most ``limit`` calls in any rolling 60 seconds, shared by every caller of this process."""

    limit: int
    clock: Callable[[], float] = time.monotonic
    _calls: deque[float] = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self) -> bool:
        now = self.clock()
        with self._lock:
            while self._calls and now - self._calls[0] >= 60:
                self._calls.popleft()
            if len(self._calls) >= self.limit:
                return False
            self._calls.append(now)
            return True

    def retry_after(self) -> int:
        with self._lock:
            if not self._calls:
                return 1
            return max(1, int(60 - (self.clock() - self._calls[0])) + 1)


@dataclass
class FeedbackStore:
    """Keeps the most recent feedback in memory. Lost on restart and not shared between instances:
    a placeholder until Week 11 stores it with the trace ID."""

    items: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=MAX_FEEDBACK_ITEMS))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, request_id: str, rating: str, comment: str) -> None:
        with self._lock:
            self.items.append({"request_id": request_id, "rating": rating, "comment": comment})


def find_web_root() -> Path | None:
    """The built React app: ``PAYRAG_WEB_DIR`` if set, else ``payments_rag/web`` (inside the
    deployed zip), else the front end's build output beside the source. None if no index exists."""
    configured = os.environ.get("PAYRAG_WEB_DIR")
    here = Path(__file__).resolve().parent
    candidates = (
        [Path(configured)] if configured else [here / "web", here.parents[1] / "frontend" / "dist"]
    )
    return next((c for c in candidates if (c / "index.html").is_file()), None)


def default_answerer() -> Answerer:
    """The production pipeline, built on first use so importing this module never calls Azure."""
    from .ask import STRATEGY, ask
    from .azure_clients import (
        AzureChatGenerator,
        AzureHybridRetriever,
        AzureOpenAIEmbedder,
        AzureSearchStore,
        AzureSettings,
    )

    settings = AzureSettings.from_env()
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings),
        AzureOpenAIEmbedder(settings),
        STRATEGY,
        semantic=True,
        semantic_fallback=True,  # keep answering if the free semantic allowance runs out
    )
    chat = AzureChatGenerator(settings)
    return lambda question: ask(question, retriever, chat)


def settings_present() -> bool:
    """True when the Azure settings are all there (names only; nothing is called or revealed)."""
    from .azure_clients import AzureSettings

    try:
        AzureSettings.from_env()
    except ValueError:
        return False
    return True


def create_app(
    answerer: Answerer | None = None,
    *,
    api_key: str | None = None,
    rate_per_minute: int = DEFAULT_RATE_PER_MINUTE,
    clock: Callable[[], float] = time.monotonic,
    configured: Callable[[], bool] = settings_present,
    serve_web: bool = True,
    web_root: Path | None = None,
) -> FastAPI:
    """Build the app. ``answerer`` defaults to the Azure pipeline, created on the first request.

    With ``serve_web`` the built React app is served at ``/`` (from ``web_root``, or found by
    ``find_web_root``), so the page and the API share one origin and need no CORS.
    """
    app = FastAPI(title="Payments knowledge assistant", version="0.1.0")
    limiter = RateLimiter(rate_per_minute, clock)
    feedback = FeedbackStore()
    cache: list[Answerer] = [] if answerer is None else [answerer]
    build_lock = threading.Lock()
    expected_key = api_key if api_key is not None else os.environ.get("PAYRAG_API_KEY") or None

    def get_answerer() -> Answerer:
        with build_lock:
            if not cache:
                cache.append(default_answerer())
            return cache[0]

    def check_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if expected_key is None:
            return
        if x_api_key is None or not hmac.compare_digest(x_api_key, expected_key):
            raise HTTPException(status_code=401, detail="missing or wrong X-API-Key")

    @app.get("/health")
    def health() -> HealthResponse:
        return HealthResponse(status="ok", configured=configured())

    @app.post("/ask", dependencies=[Depends(check_key)])
    def ask_endpoint(body: AskRequest) -> AskResponse:
        if not limiter.allow():
            raise HTTPException(
                status_code=429,
                detail="too many requests; try again shortly",
                headers={"Retry-After": str(limiter.retry_after())},
            )
        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            result = get_answerer()(body.question)
        except Exception:
            # The cause (settings, a model error) goes to the log, not to the caller.
            log.exception("request %s failed", request_id)
            raise HTTPException(
                status_code=502, detail="the assistant could not answer; try again"
            ) from None
        latency_ms = round((time.perf_counter() - started) * 1000)
        log.info("request %s refused=%s latency_ms=%d", request_id, result.refused, latency_ms)
        return AskResponse(
            request_id=request_id,
            question=body.question,
            answer=result.text,
            sources=list(result.sources),
            refused=result.refused,
            reason=result.reason,
            latency_ms=latency_ms,
        )

    @app.post("/feedback", dependencies=[Depends(check_key)])
    def feedback_endpoint(body: FeedbackRequest) -> FeedbackResponse:
        feedback.add(body.request_id, body.rating, body.comment)
        return FeedbackResponse(stored=True)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path not in NO_CSP_PATHS:
            response.headers["Content-Security-Policy"] = CSP
        return response

    app.state.feedback = feedback
    root = (web_root or find_web_root()) if serve_web else None
    if root is not None:
        # Mounted last: the API routes above and the docs pages are matched first.
        app.mount("/", StaticFiles(directory=root, html=True), name="web")
    return app


app = create_app()
