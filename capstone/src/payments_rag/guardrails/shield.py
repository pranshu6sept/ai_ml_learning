"""Azure AI Content Safety Prompt Shields: detect prompt attacks in questions and in documents.

    shield = PromptShields("https://<resource>.cognitiveservices.azure.com")
    shield("Ignore all previous instructions")              # True: a user prompt attack
    shield.analyze(question, [passage1, passage2])          # also checks documents

The service is a classifier: it returns, for the user prompt and for each document, whether an
attack is detected (``attackDetected``). It catches paraphrases and other languages that the
local patterns miss, but it is a model, so it also has false positives and misses; the report
measures both.

Authentication is keyless: a Microsoft Entra ID token (``DefaultAzureCredential``) for the scope
below, so no key is stored anywhere. The caller needs the "Cognitive Services User" role on the
resource. The resource must be in a region that offers Prompt Shields (South India does).

Request and response follow Microsoft Learn's quickstart (api-version 2024-09-01): POST
``/contentsafety/text:shieldPrompt`` with ``{"userPrompt", "documents"}``, answer
``{"userPromptAnalysis": {"attackDetected"}, "documentsAnalysis": [{"attackDetected"}]}``. Limits:
10K characters of prompt, up to five documents of 10K characters in total.

Failure policy (``fail_open``): if the service cannot be reached, the shield either lets the text
through (open, the default: the local patterns and output checks still run, and the question
service stays up) or blocks it (closed: safer, but a Content Safety outage becomes an outage of the
whole assistant). The default is a choice for a public Q&A over public documents; for anything
handling customer data, close it.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ..retrieval import Hit

API_VERSION = "2024-09-01"
SCOPE = "https://cognitiveservices.azure.com/.default"
MAX_PROMPT_CHARS = 10_000
MAX_DOCUMENTS = 5
MAX_DOCUMENT_CHARS = 10_000  # total across the documents

log = logging.getLogger("payments_rag.guardrails.shield")

Post = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]  # url, headers, body -> JSON


class ShieldError(Exception):
    """The Prompt Shields service could not be called or answered unexpectedly."""


@dataclass(frozen=True)
class ShieldResult:
    user_attack: bool
    document_attacks: tuple[bool, ...]


def _http_post(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 (https endpoint)
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # The body can echo parts of the request, so only the status goes into the error.
        raise ShieldError(f"Prompt Shields answered HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise ShieldError(f"Prompt Shields call failed: {type(error).__name__}") from None
    if not isinstance(data, dict):
        raise ShieldError("Prompt Shields returned a non-object reply")
    return data


class PromptShields:
    def __init__(
        self,
        endpoint: str,
        *,
        credential: Any = None,
        post: Post = _http_post,
        fail_open: bool = True,
    ) -> None:
        self._url = (
            f"{endpoint.rstrip('/')}/contentsafety/text:shieldPrompt?api-version={API_VERSION}"
        )
        self._credential = credential
        self._post = post
        self.fail_open = fail_open
        self.errors = 0

    def _headers(self) -> dict[str, str]:
        if self._credential is None:
            from azure.identity import DefaultAzureCredential

            self._credential = DefaultAzureCredential()
        token = self._credential.get_token(SCOPE).token
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def analyze(self, user_prompt: str, documents: Sequence[str] = ()) -> ShieldResult:
        """Raise ``ShieldError`` on failure (``__call__`` and ``screen`` apply the policy)."""
        docs = _fit(list(documents))
        body = {"userPrompt": user_prompt[:MAX_PROMPT_CHARS], "documents": docs}
        data = self._post(self._url, self._headers(), body)
        try:
            user = bool(data["userPromptAnalysis"]["attackDetected"])
            found = tuple(bool(d["attackDetected"]) for d in data.get("documentsAnalysis", []))
        except (KeyError, TypeError) as error:
            raise ShieldError("Prompt Shields reply had an unexpected shape") from error
        return ShieldResult(user, found)

    def __call__(self, text: str) -> bool:
        """The ``Shield`` protocol: True when ``text`` looks like an attack."""
        try:
            return self.analyze(text).user_attack
        except ShieldError as error:
            self.errors += 1
            log.warning(
                "prompt shield unavailable (%s); %s", error, "open" if self.fail_open else "closed"
            )
            return not self.fail_open

    def screen(self, question: str, texts: Sequence[str]) -> list[bool]:
        """For each text, True if it carries a document attack; failures follow the policy."""
        if not texts:
            return []
        try:
            result = self.analyze(question, texts)
        except ShieldError as error:
            self.errors += 1
            log.warning(
                "prompt shield unavailable (%s); %s", error, "open" if self.fail_open else "closed"
            )
            return [not self.fail_open] * len(texts)
        padded = list(result.document_attacks) + [False] * (
            len(texts) - len(result.document_attacks)
        )
        return padded[: len(texts)]


def _fit(documents: list[str]) -> list[str]:
    """At most five documents and 10K characters in total, as the service allows."""
    kept, budget = [], MAX_DOCUMENT_CHARS
    for doc in documents[:MAX_DOCUMENTS]:
        if budget <= 0:
            break
        kept.append(doc[:budget])
        budget -= len(kept[-1])
    return kept


class ShieldedRetriever:
    """A retriever whose results are screened for hidden instructions before the model sees them."""

    def __init__(self, inner: Any, shield: PromptShields) -> None:
        self._inner = inner
        self._shield = shield
        self.dropped = 0

    def search(self, query: str, top_k: int = 3) -> list[Hit]:
        hits: list[Hit] = list(self._inner.search(query, top_k))
        flags = self._shield.screen(query, [h.chunk.text for h in hits])
        kept = [h for h, attack in zip(hits, flags, strict=True) if not attack]
        self.dropped += len(hits) - len(kept)
        if len(kept) < len(hits):
            log.warning(
                "dropped %d retrieved passage(s) flagged as document attacks", len(hits) - len(kept)
            )
        return kept
