"""Compare TF-IDF and BM25, each with and without stemming, across the four chunking strategies.

Two question sets are scored separately:
* dev (questions.json): the questions used while looking at failures. Gains here are optimistic,
  because stemming was chosen after seeing which of these questions failed.
* held-out (questions_heldout.json): written before any retrieval code was changed, scored once.

BM25 uses its standard defaults (k1=1.5, b=0.75) and nothing was tuned.

Run from the repo root:  uv run python capstone/evals/evaluate_retrievers.py
"""

from __future__ import annotations

import json
from typing import Any

from evaluate_chunking import (
    HERE,
    META_SECTIONS,
    evaluate,
    load_documents,
    load_questions,
)

from payments_rag import STRATEGIES, strip_sections

RETRIEVERS: dict[str, dict[str, Any]] = {
    "tfidf": {},
    "tfidf+stem": {"stem": True},
    "bm25": {"method": "bm25"},
    "bm25+stem": {"method": "bm25", "stem": True},
}
SPLITS = {"dev": HERE / "questions.json", "heldout": HERE / "questions_heldout.json"}
if (HERE / "questions_independent.json").exists():  # written by someone who has not read the corpus
    SPLITS["independent"] = HERE / "questions_independent.json"


def table(results: dict[str, dict[str, dict]]) -> str:
    rows = [
        "| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in RETRIEVERS:
        for strategy in STRATEGIES:
            r = results[name][strategy]
            rows.append(
                f"| {name} | {strategy} | {r['hit@1']:.2f} | {r['hit@3']:.2f} | {r['hit@5']:.2f} "
                f"| {r['mrr@10']:.2f} | {r['hit@3_paraphrase']:.2f} |"
            )
    return "\n".join(rows) + "\n"


def recovered_table(results: dict[str, dict[str, dict]], hard: list[str]) -> str:
    rows = [
        f"| Retrieval | Strategy | Hard questions now in the top 3 (of {len(hard)}) |",
        "|---|---|---|",
    ]
    for name in RETRIEVERS:
        for strategy in STRATEGIES:
            missed = {m["id"] for m in results[name][strategy]["missed_or_below_rank_3"]}
            found = [q for q in hard if q not in missed]
            rows.append(f"| {name} | {strategy} | {len(found)} ({', '.join(found) or 'none'}) |")
    return "\n".join(rows) + "\n"


def separability(results: dict[str, dict[str, dict]]) -> str:
    rows = [
        "| Retrieval | Mean top score, answerable | Mean top score, unanswerable | Ratio |",
        "|---|---|---|---|",
    ]
    for name in RETRIEVERS:
        r = results[name]["structure_aware"]
        a, u = r["mean_top_score_answerable"], r["mean_top_score_unanswerable"]
        rows.append(f"| {name} | {a:.3f} | {u:.3f} | {u / a:.2f} |")
    return "\n".join(rows) + "\n"


def main() -> None:
    raw = load_documents()
    docs = {name: strip_sections(text, META_SECTIONS) for name, text in raw.items()}

    all_results: dict[str, dict[str, dict[str, dict]]] = {}
    for split, path in SPLITS.items():
        questions = load_questions(docs, path)
        all_results[split] = {
            name: {s: evaluate(s, docs, questions, options) for s in STRATEGIES}
            for name, options in RETRIEVERS.items()
        }

    base = all_results["dev"]["tfidf"]
    missed_by_all = set.intersection(
        *({m["id"] for m in base[s]["missed_or_below_rank_3"]} for s in STRATEGIES)
    )
    hard = sorted(missed_by_all)

    counts = {}
    for split, path in SPLITS.items():
        qs = json.loads(path.read_text(encoding="utf-8"))
        counts[split] = (sum(bool(q["gold"]) for q in qs), sum(not q["gold"] for q in qs))
    independent = ""
    if "independent" in all_results and counts["independent"][0]:
        answerable, unanswerable = counts["independent"]
        independent = (
            f"## Independent set ({answerable} answerable, {unanswerable} unanswerable; "
            f"one question = {1 / answerable:.3f})\n\n"
            "Written by someone who had not read the corpus: the most trustworthy numbers here.\n\n"
            f"{table(all_results['independent'])}\n"
        )
    text = (
        "BM25 uses its standard defaults (k1=1.5, b=0.75); nothing was tuned. Stemming is the "
        "Snowball "
        "English stemmer. Meta sections are removed at ingestion. Chunks target about 80 words.\n\n"
        f"## Dev set ({counts['dev'][0]} answerable, {counts['dev'][1]} unanswerable; "
        f"one question = {1 / counts['dev'][0]:.3f})\n\n"
        "Used while choosing these fixes, so gains here are optimistic.\n\n"
        f"{table(all_results['dev'])}\n"
        f"## Held-out set ({counts['heldout'][0]} answerable, {counts['heldout'][1]} unanswerable; "
        f"one question = {1 / counts['heldout'][0]:.3f})\n\n"
        "Written before any retrieval change and scored once.\n\n"
        f"{table(all_results['heldout'])}\n"
        f"{independent}"
        "## Dev questions that every strategy missed with plain TF-IDF\n\n"
        f"{recovered_table(all_results['dev'], hard)}\n"
        "## Can the top score tell answerable from unanswerable? (dev set, structure_aware)\n\n"
        "A ratio above 1 means unanswerable questions scored higher than answerable ones.\n\n"
        f"{separability(all_results['dev'])}"
    )
    (HERE / "retrievers_eval.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    (HERE / "retrievers_eval.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
