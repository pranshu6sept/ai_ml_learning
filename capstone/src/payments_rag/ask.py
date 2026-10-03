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
from .ingestion import load_registry
from .retrieval import Hit
from .search_filters import SearchFilter

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


def _known(
    parser: argparse.ArgumentParser, flag: str, given: list[str], valid: list[str]
) -> tuple[str, ...]:
    """Match each value to the registry spelling, ignoring case; unknown values are an error."""
    canonical = {v.lower(): v for v in valid}
    unknown = [v for v in given if v.lower() not in canonical]
    if unknown:
        parser.error(f"{flag}: unknown {unknown}; choose from {sorted(canonical.values())}")
    return tuple(canonical[v.lower()] for v in given)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask a question about the payments corpus.")
    parser.add_argument("question")
    parser.add_argument("--no-semantic", action="store_true", help="skip Azure's semantic ranker")
    parser.add_argument(
        "--source", action="append", default=[], help="only this document (repeatable)"
    )
    parser.add_argument(
        "--region", action="append", default=[], help="only this region (repeatable)"
    )
    parser.add_argument("--published-from", help="only documents published on or after YYYY-MM-DD")
    parser.add_argument("--published-to", help="only documents published on or before YYYY-MM-DD")
    args = parser.parse_args(argv)
    sources = load_registry()
    filters = SearchFilter(
        doc_ids=_known(parser, "--source", args.source, [s.doc_id for s in sources]),
        jurisdictions=_known(parser, "--region", args.region, [s.jurisdiction for s in sources]),
        published_from=args.published_from,
        published_to=args.published_to,
    )
    settings = AzureSettings.from_env()
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings),
        AzureOpenAIEmbedder(settings),
        STRATEGY,
        semantic=not args.no_semantic,
        filters=filters,
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
