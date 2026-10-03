# ruff: noqa: E501
"""First live check of the Azure setup: auth, embeddings, search index, grounded answer.

Run after infra/deploy.ps1:   uv run --all-groups python capstone/evals/azure_smoke_test.py
Each step prints OK or FAIL with the most likely cause. It uploads this repo's corpus to your search
index (a few dozen small documents) and makes one chat call, which costs a tiny amount of tokens.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from evaluate_chunking import META_SECTIONS, chunk_corpus, load_documents

from payments_rag import (
    STRATEGIES,
    AzureChatGenerator,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    GroundedAnswer,
    strip_sections,
)

HINTS = {
    "DefaultAzureCredential failed": "Could not sign in. Run `az login`, and make sure `az` is on this "
    "terminal's PATH (reopen the terminal after installing the CLI).",
    "401": "Not authenticated: run `az login`. For Azure AI Search, role-based access must be enabled "
    "(the Bicep does this).",
    "403": "Signed in but not authorised. Role assignments can take several minutes to apply; wait and retry.",
    "404": "Deployment or resource not found: check the names in .env against the portal.",
    "429": "Rate limited: the deployment capacity is small; wait a minute and retry.",
    "QuotaNotMet": "No Azure OpenAI quota for that model here; see the quota check in infra/README.md.",
    "DeploymentNotFound": "The model deployment name in .env does not exist in the Azure OpenAI resource.",
}


def step(name: str, action: Callable[[], Any]) -> Any:
    try:
        result = action()
    except Exception as error:  # noqa: BLE001 - we want to report any failure plainly
        text = f"{type(error).__name__}: {error}"
        hint = next((h for key, h in HINTS.items() if key in text), "See the error above.")
        print(f"FAIL  {name}\n      {text[:300]}\n      Hint: {hint}")
        sys.exit(1)
    print(f"OK    {name}")
    return result


def main() -> None:
    settings = step("read settings (.env / environment)", AzureSettings.from_env)
    print(f"      OpenAI: {settings.openai_endpoint}\n      Search: {settings.search_endpoint}")

    embedder = AzureOpenAIEmbedder(settings)
    vectors = step("embed a sentence with Azure OpenAI", lambda: embedder(["card payment"]))
    print(f"      got a vector of {vectors.shape[1]} numbers")

    store = AzureSearchStore(settings)
    step("create or update the search index", store.ensure_index)

    docs = {n: strip_sections(t, META_SECTIONS) for n, t in load_documents().items()}
    chunks = [c for strategy in STRATEGIES for c in chunk_corpus(docs, strategy)]
    step(
        f"embed and upload {len(chunks)} chunks",
        lambda: store.upload(chunks, embedder([c.text for c in chunks])),
    )
    print("      (the index can take a few seconds to show new documents)")

    question = "Can shops charge extra for paying by card in the EU?"
    vector = embedder([question])[0]
    hits = step(
        "hybrid search (keyword + vector)",
        lambda: store.search(question, vector, top_k=3, strategy="structure_aware"),
    )
    for hit in hits:
        print(f"      {hit.score:.3f}  {hit.chunk.doc_id} > {hit.chunk.section}")
    if not hits:
        print("      no results yet: wait a few seconds and run again")
        return

    generator = AzureChatGenerator(settings)
    answer = GroundedAnswer(question, False, tuple(hits), "smoke test")
    reply = step("generate a grounded answer with Azure OpenAI", lambda: generator.generate(answer))
    print(f"      Q: {question}\n      A: {reply}")
    for citation in answer.citations():
        print(f"      {citation}")
    print("\nAll steps passed.")


if __name__ == "__main__":
    main()
