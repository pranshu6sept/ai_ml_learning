"""Ask one question and get a cited answer from the Azure index (Week 4 retrieve -> generate).

    uv run --all-groups python -m payments_rag.ask "What does pacs.008 do?"

Steps: Azure hybrid search with the semantic ranker (top 3) -> a quote-verified answerability check
(the model must say the passages fully answer AND quote a sentence that really is in them) -> a
cited answer, or a refusal. The index must exist (`python -m payments_rag.indexing`).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Protocol

from .azure_clients import (
    AzureChatGenerator,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
)
from .grounding import NO_ANSWER, GroundedAnswer
from .retrieval import Hit

STRATEGY = "structure_aware"
TOP_K = 3


class Searcher(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[Hit]: ...


@dataclass(frozen=True)
class Answer:
    """The reply to show, the sources behind it, and why the assistant answered or refused."""

    question: str
    text: str
    sources: tuple[str, ...]
    refused: bool
    reason: str


def ask(
    question: str, retriever: Searcher, generator: AzureChatGenerator, *, top_k: int = TOP_K
) -> Answer:
    """Retrieve, check the passages really answer the question, then answer with citations."""
    hits = tuple(retriever.search(question, top_k))
    if not hits:
        return Answer(question, NO_ANSWER, (), True, "nothing in the corpus matched the question")
    verdict = generator.check_answerability(question, hits)
    if not verdict.can_answer:
        reason = f"the passages were judged '{verdict.label}'" + (
            "" if verdict.quote_found or verdict.label != "full" else " but its quote was not found"
        )
        return Answer(question, NO_ANSWER, (), True, reason)
    grounded = GroundedAnswer(question, False, hits, "passages judged to answer the question")
    reply = generator.generate_cited(grounded)
    if reply.refused:
        return Answer(
            question, NO_ANSWER, (), True, "the model declined to answer from the passages"
        )
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", reply.text)}
    sources = tuple(
        label for n, label in enumerate(grounded.citations(), 1) if n in cited
    )  # only passages the answer actually cites
    return Answer(question, reply.text, sources, False, grounded.reason)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask a question about the payments corpus.")
    parser.add_argument("question")
    parser.add_argument("--no-semantic", action="store_true", help="skip Azure's semantic ranker")
    args = parser.parse_args(argv)
    settings = AzureSettings.from_env()
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings),
        AzureOpenAIEmbedder(settings),
        STRATEGY,
        semantic=not args.no_semantic,
    )
    result = ask(args.question, retriever, AzureChatGenerator(settings))
    print(result.text)
    if result.sources:
        print("\nSources:")
        for source in result.sources:
            print(f"  {source}")
    else:
        print(f"\n(refused: {result.reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
