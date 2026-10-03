"""Compare the four chunking strategies on retrieval quality, with a ground truth that is checked.

A question is answered correctly when one of the top-k retrieved chunks (a) comes from the expected
document and (b) contains the exact gold phrase that answers it. That is stricter than checking
for keywords, and it cannot be satisfied by a chunk that merely repeats the question.

Run from the repo root:  uv run python capstone/evals/evaluate_chunking.py
Writes chunking_eval.json and chunking_eval.md next to this file.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from payments_rag import STRATEGIES, Chunk, Retriever, chunk_document, strip_sections
from payments_rag.indexing import CHUNK_WORDS, MAX_SENTENCES, OVERLAP
from payments_rag.ingestion import META_SECTIONS, SourceDocument, load_registry

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "docs" / "corpus"
QUESTIONS = HERE / "questions.json"
KS = (1, 3, 5)
MAX_RANK = 10
# Sections that only describe the corpus or list sample questions; they are not knowledge.


def normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def load_sources() -> list[SourceDocument]:
    """The validated registry (raises RegistryError if sources.json and the files disagree)."""
    return load_registry(CORPUS)


def load_documents() -> dict[str, str]:
    """Raw text of every registered document, keyed by file stem."""
    return {
        source.doc_id: (CORPUS / source.file).read_text(encoding="utf-8")
        for source in load_sources()
    }


def load_questions(documents: dict[str, str], path: Path = QUESTIONS) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    normalized = {doc_id: normalize(text) for doc_id, text in documents.items()}
    for question in questions:
        for gold in question["gold"]:
            if normalize(gold["phrase"]) not in normalized[gold["doc"]]:
                raise ValueError(f"{question['id']}: gold phrase not found in {gold['doc']}")
    return questions


def is_relevant(chunk: Chunk, question: dict[str, Any]) -> bool:
    text = normalize(chunk.text)
    return any(
        gold["doc"] == chunk.doc_id and normalize(gold["phrase"]) in text
        for gold in question["gold"]
    )


def chunk_corpus(documents: dict[str, str], strategy: str) -> list[Chunk]:
    sources = {source.doc_id: source for source in load_sources()}
    chunks: list[Chunk] = []
    for doc_id, text in documents.items():
        source = sources[doc_id]
        chunks.extend(
            chunk_document(
                text,
                doc_id=doc_id,
                strategy=strategy,
                title=source.title,
                source_url=source.url,
                chunk_size=CHUNK_WORDS,
                overlap=OVERLAP,
                max_sentences=MAX_SENTENCES,
            )
        )
    return chunks


def evaluate(
    strategy: str,
    documents: dict[str, str],
    questions: list[dict[str, Any]],
    retriever_options: dict[str, Any] | None = None,
    retriever_factory: Callable[[list[Chunk]], Any] | None = None,
) -> dict:
    chunks = chunk_corpus(documents, strategy)
    started = time.perf_counter()
    if retriever_factory is not None:
        retriever = retriever_factory(chunks)
    else:
        retriever = Retriever(chunks, **(retriever_options or {}))
    build_ms = (time.perf_counter() - started) * 1000

    answerable = [q for q in questions if q["gold"]]
    unanswerable = [q for q in questions if not q["gold"]]

    hits = {k: 0 for k in KS}
    reciprocal_ranks: list[float] = []
    intact = 0
    top_scores: list[float] = []
    misses: list[dict[str, Any]] = []
    latencies: list[float] = []

    for question in answerable:
        if any(is_relevant(chunk, question) for chunk in chunks):
            intact += 1
        started = time.perf_counter()
        results = retriever.search(question["question"], top_k=MAX_RANK)
        latencies.append((time.perf_counter() - started) * 1000)
        top_scores.append(results[0].score if results else 0.0)
        rank = next((i for i, hit in enumerate(results, 1) if is_relevant(hit.chunk, question)), 0)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        for k in KS:
            hits[k] += int(0 < rank <= k)
        if not rank or rank > 3:
            top = results[0] if results else None
            misses.append(
                {
                    "id": question["id"],
                    "kind": question["kind"],
                    "question": question["question"],
                    "rank_of_first_correct_chunk": rank or None,
                    "top_chunk_section": top.chunk.section if top else None,
                    "top_chunk_doc": top.chunk.doc_id if top else None,
                    "top_score": round(top.score, 3) if top else 0.0,
                }
            )

    unanswerable_scores = []
    for question in unanswerable:
        results = retriever.search(question["question"], top_k=1)
        unanswerable_scores.append(results[0].score if results else 0.0)

    def by_kind(kind: str) -> float:
        subset = [q for q in answerable if q["kind"] == kind]
        found = 0
        for question in subset:
            results = retriever.search(question["question"], top_k=3)
            found += int(any(is_relevant(h.chunk, question) for h in results))
        return found / len(subset) if subset else float("nan")  # no question of this kind

    words = [chunk.word_count for chunk in chunks]
    n = len(answerable)
    return {
        "strategy": strategy,
        "chunks": len(chunks),
        "words_min_median_max": [min(words), int(statistics.median(words)), max(words)],
        "tiny_chunks_under_15_words": sum(w < 15 for w in words),
        "gold_phrase_intact": intact / n,
        **{f"hit@{k}": hits[k] / n for k in KS},
        "mrr@10": sum(reciprocal_ranks) / n,
        "hit@3_direct": by_kind("direct"),
        "hit@3_paraphrase": by_kind("paraphrase"),
        "mean_top_score_answerable": sum(top_scores) / n,
        "mean_top_score_unanswerable": sum(unanswerable_scores) / len(unanswerable_scores),
        "index_build_ms": round(build_ms, 2),
        "query_ms_mean": round(sum(latencies) / len(latencies), 3),
        "missed_or_below_rank_3": misses,
    }


def render_table(results: dict[str, dict]) -> str:
    rows = [
        "| Strategy | Chunks | Words (min/med/max) | Gold phrase intact | Hit@1 | Hit@3 | Hit@5 "
        "| MRR@10 | Hit@3 direct | Hit@3 paraphrase |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in STRATEGIES:
        r = results[name]
        low, mid, high = r["words_min_median_max"]
        rows.append(
            f"| {name} | {r['chunks']} | {low}/{mid}/{high} | {r['gold_phrase_intact']:.2f} "
            f"| {r['hit@1']:.2f} | {r['hit@3']:.2f} | {r['hit@5']:.2f} | {r['mrr@10']:.2f} "
            f"| {r['hit@3_direct']:.2f} | {r['hit@3_paraphrase']:.2f} |"
        )
    scores = [
        "| Strategy | Mean top score, answerable | Mean top score, unanswerable | "
        "Index build (ms) | Query (ms, mean) |",
        "|---|---|---|---|---|",
    ]
    for name in STRATEGIES:
        r = results[name]
        scores.append(
            f"| {name} | {r['mean_top_score_answerable']:.3f} "
            f"| {r['mean_top_score_unanswerable']:.3f} "
            f"| {r['index_build_ms']} | {r['query_ms_mean']} |"
        )
    return "\n".join(rows) + "\n\n" + "\n".join(scores) + "\n"


def render_report(all_results: dict[str, dict[str, dict]], questions: list[dict[str, Any]]) -> str:
    counts = {
        kind: sum(q["kind"] == kind for q in questions)
        for kind in ("direct", "paraphrase", "unanswerable")
    }
    answerable = counts["direct"] + counts["paraphrase"]
    out = [
        f"{answerable} answerable questions ({counts['direct']} direct, "
        f"{counts['paraphrase']} paraphrased) and {counts['unanswerable']} "
        "the corpus cannot answer. "
        f"Chunks target about {CHUNK_WORDS} words ({MAX_SENTENCES} sentences for semantic). "
        "Retrieval is TF-IDF, top-k over all four documents. One question is worth "
        f"{1 / (counts['direct'] + counts['paraphrase']):.3f} of any score.\n"
    ]
    titles = {
        "as_is": "Corpus as written (includes the meta sections that list sample questions)",
        "meta_removed": f"Meta sections removed at ingestion ({', '.join(META_SECTIONS)})",
    }
    for variant, results in all_results.items():
        out.append(f"## {titles[variant]}\n\n{render_table(results)}")
    return "\n".join(out)


def main() -> None:
    documents = load_documents()
    variants = {
        "as_is": documents,
        "meta_removed": {d: strip_sections(t, META_SECTIONS) for d, t in documents.items()},
    }
    questions = load_questions(documents)
    all_results: dict[str, dict[str, dict]] = {}
    for variant, docs in variants.items():
        load_questions(docs)  # the gold phrases must survive the cleaning
        all_results[variant] = {name: evaluate(name, docs, questions) for name in STRATEGIES}
    (HERE / "chunking_eval.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    text = render_report(all_results, questions)
    (HERE / "chunking_eval.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
