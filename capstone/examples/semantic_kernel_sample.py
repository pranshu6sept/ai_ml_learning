# ruff: noqa: E501
"""A small Semantic Kernel sample: the payments search as a plugin the model can call.

Semantic Kernel (SK) is Microsoft's orchestration SDK. This sample shows its three core ideas on the
same corpus the LangGraph pipeline uses:

* a **plugin**: an ordinary Python class whose methods, marked with ``@kernel_function``, SK describes
  to the model (name, description, argument types);
* **automatic function calling**: ``FunctionChoiceBehavior.Auto()`` lets the model decide which plugin
  functions to call, and how many times, before it answers. This replaces the older "planner" classes
  (Handlebars and Stepwise planners), which SK deprecated in favour of the model's native tool calling;
* a **filter**: a hook that runs around every function call, used here to print what the model called.

It is a sample, not part of the capstone pipeline: there is no validation, no refusal check and no
evaluation here. The LangGraph version in `payments_rag.graph` is the one that is measured.

Run it in a throwaway environment, because Semantic Kernel is a large dependency this repo does not use:

    uv run --no-project --python 3.11 --with semantic-kernel --with azure-identity \\
        --with azure-search-documents --with numpy --with snowballstemmer --with pydantic \\
        python capstone/examples/semantic_kernel_sample.py "What is remittance information?"

Needs `az login` and the deployed Azure resources (settings are read from `.env`).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "capstone" / "src"))

from azure.identity import DefaultAzureCredential  # noqa: E402
from semantic_kernel import Kernel  # noqa: E402
from semantic_kernel.connectors.ai import FunctionChoiceBehavior  # noqa: E402
from semantic_kernel.connectors.ai.open_ai import (  # noqa: E402
    AzureChatCompletion,
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory  # noqa: E402
from semantic_kernel.filters import FilterTypes, FunctionInvocationContext  # noqa: E402
from semantic_kernel.functions import kernel_function  # noqa: E402

from payments_rag import (  # noqa: E402
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
)
from payments_rag.ingestion import load_registry  # noqa: E402

SYSTEM_PROMPT = (
    "You answer questions about banking and payments using only the passages returned by the "
    "search_corpus function. Search before answering. Cite passages like [1]. If the passages do not "
    "contain the answer, say you do not know."
)


class PaymentsPlugin:
    """The functions the model may call."""

    def __init__(self, retriever: AzureHybridRetriever) -> None:
        self._retriever = retriever

    @kernel_function(
        name="search_corpus",
        description="Search the payments documents and return the top numbered passages with sources.",
    )
    def search_corpus(self, query: Annotated[str, "a short search query"]) -> str:
        hits = self._retriever.search(query, 3)
        if not hits:
            return "No passages found."
        return "\n\n".join(
            f"[{n}] ({h.chunk.doc_id} > {h.chunk.section or 'document'}) {h.chunk.text}"
            for n, h in enumerate(hits, 1)
        )

    @kernel_function(
        name="list_documents",
        description="List the titles of the documents the corpus contains.",
    )
    def list_documents(self) -> str:
        return "\n".join(f"- {s.title} ({s.jurisdiction})" for s in load_registry())


async def log_calls(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]],
) -> None:
    """A filter: runs around every function call, so we can see what the model chose to do."""
    arguments = {k: v for k, v in context.arguments.items() if v is not None}
    print(f"  model called {context.function.plugin_name}.{context.function.name}({arguments})")
    await next(context)


async def main(question: str) -> None:
    settings = AzureSettings.from_env()
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings),
        AzureOpenAIEmbedder(settings),
        "structure_aware",
        semantic=True,
    )
    kernel = Kernel()
    kernel.add_service(
        AzureChatCompletion(
            deployment_name=settings.chat_deployment,
            endpoint=settings.openai_endpoint,
            api_version=settings.openai_api_version,
            credential=DefaultAzureCredential(),
        )
    )
    kernel.add_plugin(PaymentsPlugin(retriever), plugin_name="payments")
    kernel.add_filter(FilterTypes.FUNCTION_INVOCATION, log_calls)

    execution = AzureChatPromptExecutionSettings(
        function_choice_behavior=FunctionChoiceBehavior.Auto()
    )
    history = ChatHistory(system_message=SYSTEM_PROMPT)
    history.add_user_message(question)

    print(f"question: {question}")
    reply = await kernel.get_service(type=AzureChatCompletion).get_chat_message_content(
        history, execution, kernel=kernel
    )
    print(f"\n{reply}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "What is remittance information?"))
