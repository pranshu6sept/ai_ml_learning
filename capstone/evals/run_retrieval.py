"""Week 5 retrieval evaluation on the golden set: recall@k, MRR and nDCG by chunking strategy.

Runs offline (no Azure, no cost) with three local retrievers over the four chunking strategies, on
the answerable questions of ``golden_set.jsonl`` and on each split separately. With ``--azure`` it
also scores the Azure index (hybrid, and hybrid + semantic ranker; the semantic ranker uses the
free tier's monthly query allowance).

    uv run --all-groups python capstone/evals/run_retrieval.py [--azure]

Writes ``results/retrieval.md`` and ``results/retrieval.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from evaluate_chunking import HERE, META_SECTIONS, evaluate, load_documents, normalize

from payments_rag import STRATEGIES, Retriever, SentenceTransformerEmbedder, strip_sections

GOLDEN = HERE / "golden_set.jsonl"
RESULTS = HERE / "results"
METRICS = ("hit@1", "hit@3", "recall@1", "recall@3", "recall@5", "mrr@10", "ndcg@3", "ndcg@5")


def load_golden(documents: dict[str, str]) -> list[dict[str, Any]]:
    """The golden set; every gold phrase must still be in its document after cleaning."""
    normalized = {doc: normalize(text) for doc, text in documents.items()}
    golden = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line]
    for q in golden:
        for gold in q["gold"]:
            if normalize(gold["phrase"]) not in normalized[gold["doc"]]:
                raise ValueError(f"{q['id']}: gold phrase not found in {gold['doc']}")
    return golden


def local_retrievers() -> dict[str, Callable[[list[Any]], Any]]:
    embedder = SentenceTransformerEmbedder()
    return {
        "tfidf": lambda chunks: Retriever(chunks),
        "bm25+stem": lambda chunks: Retriever(chunks, method="bm25", stem=True),
        "hybrid (bm25+stem, embedding)": lambda chunks: Retriever(
            chunks, method="hybrid", stem=True, embedder=embedder
        ),
    }


def azure_retrievers() -> dict[str, Callable[[list[Any]], Any]]:
    from payments_rag import (
        AzureHybridRetriever,
        AzureOpenAIEmbedder,
        AzureSearchStore,
        AzureSettings,
    )

    settings = AzureSettings.from_env()
    store, embedder = AzureSearchStore(settings), AzureOpenAIEmbedder(settings)
    return {
        "azure hybrid": lambda _c: AzureHybridRetriever(store, embedder, "structure_aware"),
        "azure hybrid + semantic ranker": lambda _c: AzureHybridRetriever(
            store, embedder, "structure_aware", semantic=True
        ),
    }


def row(name: str, r: dict[str, Any]) -> str:
    return f"| {name} | " + " | ".join(f"{r[m]:.2f}" for m in METRICS) + " |"


HEADER = (
    "| {first} | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |\n"
    "|---|---|---|---|---|---|---|---|---|"
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--azure", action="store_true", help="also score the Azure index")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # answers contain characters such as the rupee sign

    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = load_golden(documents)
    splits = sorted({q["split"] for q in golden if q["split"] != "abstain"})
    answerable = [q for q in golden if q["expected"] == "answer"]
    refuse = [q for q in golden if q["expected"] == "refuse"]

    results: dict[str, dict[str, dict[str, Any]]] = {}  # retriever -> strategy -> metrics
    for name, factory in local_retrievers().items():
        results[name] = {
            s: evaluate(s, documents, answerable + refuse, retriever_factory=factory)
            for s in STRATEGIES
        }
    per_split: dict[str, dict[str, dict[str, Any]]] = {}  # retriever -> split -> metrics
    factories = dict(local_retrievers())
    if args.azure:
        for name, factory in azure_retrievers().items():
            results[name] = {
                "structure_aware": evaluate(
                    "structure_aware", documents, answerable + refuse, retriever_factory=factory
                )
            }
            factories[name] = factory
    for name in factories:
        strategy = "structure_aware"
        per_split[name] = {
            split: evaluate(
                strategy,
                documents,
                [q for q in answerable if q["split"] == split],
                retriever_factory=factories[name],
            )
            for split in splits
        }

    n_split = {s: sum(q["split"] == s for q in answerable) for s in splits}
    out = [
        f"Golden set: {len(golden)} questions, {len(answerable)} answerable "
        f"({', '.join(f'{s} {n}' for s, n in n_split.items())}) and {len(refuse)} to refuse. "
        "Ranking metrics use the answerable questions only. One question is worth "
        f"{1 / len(answerable):.3f} of a score on the full set.\n",
        "Recall@k is the share of a question's gold passages covered by the top k chunks "
        "(a question with two acceptable passages scores 0.5 if only one is found); Hit@k is "
        "satisfied by either. nDCG@k rewards putting every relevant chunk high.\n",
        "## All answerable questions: every retriever x every chunking strategy\n",
        HEADER.format(first="Retriever, strategy"),
    ]
    for name, by_strategy in results.items():
        for strategy, r in by_strategy.items():
            out.append(row(f"{name}, {strategy}", r))
    out += [
        "",
        "## By question set (structure-aware chunks)\n",
        "Dev questions were used to build and tune the pipeline, so they flatter it; held-out, "
        "corpus_update and independent were not. Small sets are noisy.\n",
    ]
    for split in splits:
        out += [f"### {split} ({n_split[split]} questions)\n", HEADER.format(first="Retriever")]
        for name in factories:
            out.append(row(name, per_split[name][split]))
        out.append("")
    text = "\n".join(out)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "retrieval.md").write_text(text, encoding="utf-8")
    slim = {
        k: {s: {m: round(r[m], 4) for m in METRICS} | {"chunks": r["chunks"]} for s, r in v.items()}
        for k, v in results.items()
    }
    slim_split = {
        k: {s: {m: round(r[m], 4) for m in METRICS} for s, r in v.items()}
        for k, v in per_split.items()
    }
    (RESULTS / "retrieval.json").write_text(
        json.dumps({"all": slim, "by_split": slim_split}, indent=2), encoding="utf-8"
    )
    print(text)


if __name__ == "__main__":
    main()
