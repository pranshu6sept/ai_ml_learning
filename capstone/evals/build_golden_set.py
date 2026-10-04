"""Merge the question files and the reference answers into one golden set: ``golden_set.jsonl``.

The golden set is what the Week 5 evaluation runs on. Each line has the question, the expected
source passages (``gold``: a document and a phrase that must appear in the retrieved chunk, which
works for every chunking strategy), and a reference answer written from those passages. Questions
the corpus cannot answer have ``expected: "refuse"`` and no reference answer.

    uv run python capstone/evals/build_golden_set.py

Inputs: ``questions*.json`` (the sets used so far) and ``golden_references.json`` (id -> reference
answer, written by hand from the gold passages). The 35 unanswerable web questions in
``questions_independent.json`` are left out: they serve the abstention study, and keeping them out
holds the set at 95 questions.
"""

from __future__ import annotations

import json

from evaluate_chunking import HERE, load_documents, load_questions

FILES = {
    "dev": "questions.json",
    "heldout": "questions_heldout.json",
    "corpus_update": "questions_corpus_update.json",
    "independent": "questions_independent.json",
    "abstain": "questions_abstain.json",
}
OUT = HERE / "golden_set.jsonl"


def build() -> list[dict]:
    documents = load_documents()
    references: dict[str, str] = json.loads(
        (HERE / "golden_references.json").read_text(encoding="utf-8")
    )
    golden: list[dict] = []
    for split, name in FILES.items():
        for q in load_questions(documents, HERE / name):  # checks every gold phrase exists
            if split == "independent" and not q["gold"]:
                continue
            answerable = bool(q["gold"])
            entry = {
                "id": q["id"],
                "split": split,
                "kind": q["kind"],
                "question": q["question"],
                "expected": "answer" if answerable else "refuse",
                "gold": q["gold"],
                "reference_answer": references.get(q["id"]) if answerable else None,
            }
            if "source" in q:
                entry["source"] = q["source"]
            golden.append(entry)
    missing = [e["id"] for e in golden if e["expected"] == "answer" and not e["reference_answer"]]
    answerable_ids = {e["id"] for e in golden if e["expected"] == "answer"}
    extra = sorted(set(references) - answerable_ids)
    if missing or extra:
        raise SystemExit(f"references missing for {missing}; references with no question: {extra}")
    return golden


def main() -> None:
    golden = build()
    OUT.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in golden) + "\n", encoding="utf-8"
    )
    answerable = sum(e["expected"] == "answer" for e in golden)
    print(
        f"wrote {len(golden)} questions to {OUT.name}: {answerable} answerable, "
        f"{len(golden) - answerable} to refuse"
    )


if __name__ == "__main__":
    main()
