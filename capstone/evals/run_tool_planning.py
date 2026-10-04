# ruff: noqa: E501
"""How good are the model's tool-call arguments for `search_corpus`?

Two measurements of the planning step (the model chooses query, region and date filters by calling
a tool), neither of which needs a search:

1. Argument accuracy on `planning_questions.json` (18 questions I labelled before running it):
   did it choose exactly the expected regions, and did it set a date limit exactly when expected?
2. Collateral damage on the golden set: for each of the 69 answerable golden questions, would the
   filters the model chose still let the gold document through? A filter that excludes the gold
   document makes the question unanswerable, which is the real risk of letting a model choose filters.
   (Documents with no published date are excluded by any date filter, and `India` does not match
   `global`.)

    uv run --all-groups python capstone/evals/run_tool_planning.py

Writes `results/tool_planning.md|json`. Needs `az login`. Calls are spaced to respect the deployment's
request limit.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from evaluate_chunking import HERE, META_SECTIONS, load_documents
from run_retrieval import RESULTS, load_golden

from payments_rag import AzureChatGenerator, AzureSettings, SearchFilter, strip_sections
from payments_rag.graph.nodes import PLAN_PROMPT
from payments_rag.ingestion import load_registry
from payments_rag.tools import to_filter

SPACING_S = 2.2  # about 27 requests a minute


def passes(flt: SearchFilter, jurisdiction: str, published: str | None) -> bool:
    """Would a document with this region and date survive the filter?"""
    if flt.jurisdictions and jurisdiction not in flt.jurisdictions:
        return False
    if flt.published_from and not (published and published >= flt.published_from):
        return False
    return not (flt.published_to and not (published and published <= flt.published_to))


def plan(chat: AzureChatGenerator, question: str) -> tuple[SearchFilter, str]:
    args = chat.plan_search(PLAN_PROMPT.format(question=question))
    time.sleep(SPACING_S)
    return to_filter(args), args.query


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    settings = AzureSettings.from_env()
    chat = AzureChatGenerator(settings)

    labelled = json.loads((HERE / "planning_questions.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for q in labelled:
        flt, query = plan(chat, q["question"])
        has_date = bool(flt.published_from or flt.published_to)
        rows.append(
            {
                "id": q["id"],
                "question": q["question"],
                "expected_regions": q["jurisdictions"],
                "chosen_regions": list(flt.jurisdictions),
                "expected_date": q["date"],
                "chosen_date": has_date,
                "published_from": flt.published_from,
                "published_to": flt.published_to,
                "query": query,
                "regions_ok": sorted(flt.jurisdictions) == sorted(q["jurisdictions"]),
                "date_ok": has_date == q["date"],
            }
        )
        print(f"[{q['id']}] regions {flt.jurisdictions} date {has_date}", flush=True)

    registry = {s.doc_id: s for s in load_registry()}
    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = [q for q in load_golden(documents) if q["expected"] == "answer"]
    damage: list[dict[str, Any]] = []
    filtered = 0
    for q in golden:
        flt, query = plan(chat, q["question"])
        if not flt.is_empty():
            filtered += 1
        gold_docs = {g["doc"] for g in q["gold"]}
        survive = [
            d for d in gold_docs if passes(flt, registry[d].jurisdiction, registry[d].published)
        ]
        damage.append(
            {
                "id": q["id"],
                "question": q["question"],
                "chosen_regions": list(flt.jurisdictions),
                "published_from": flt.published_from,
                "published_to": flt.published_to,
                "gold_docs": sorted(gold_docs),
                "gold_survives": bool(survive),
                "filtered": not flt.is_empty(),
            }
        )
        print(
            f"[{q['id']}] filtered={not flt.is_empty()} gold_survives={bool(survive)}", flush=True
        )

    n = len(rows)
    regions_ok = sum(r["regions_ok"] for r in rows)
    date_ok = sum(r["date_ok"] for r in rows)
    both = sum(r["regions_ok"] and r["date_ok"] for r in rows)
    excluded = [d for d in damage if not d["gold_survives"]]
    lines = [
        "The model chooses search filters by calling a `search_corpus` tool (forced, arguments validated). Judge: me, against labels I wrote before the run. "
        "One run, small sets: one question is worth 5.6 points on the labelled set.\n",
        "## 1. Argument accuracy (18 labelled questions)\n",
        "| Measure | Correct |",
        "|---|---|",
        f"| Regions exactly as expected | {regions_ok} of {n} |",
        f"| Date limit set exactly when expected | {date_ok} of {n} |",
        f"| Both | {both} of {n} |",
        "",
        "Mistakes:\n",
    ]
    wrong = [r for r in rows if not (r["regions_ok"] and r["date_ok"])]
    lines += [
        f"- {r['id']} {r['question']}\n  expected regions {r['expected_regions']} date {r['expected_date']}; "
        f"chose regions {r['chosen_regions']} date {r['chosen_date']} (from {r['published_from']}, to {r['published_to']})"
        for r in wrong
    ] or ["none"]
    lines += [
        "",
        f"## 2. Would the chosen filters exclude the gold document? ({len(golden)} answerable golden questions)\n",
        "| Measure | Count |",
        "|---|---|",
        f"| Questions where the model set any filter | {filtered} of {len(golden)} |",
        f"| Questions where the filter would exclude every gold document | {len(excluded)} of {len(golden)} |",
        "",
        "Questions whose gold document the filter would exclude (these become unanswerable if the filter is trusted):\n",
    ]
    lines += [
        f"- {d['id']} {d['question']}\n  chose regions {d['chosen_regions']} from {d['published_from']} to {d['published_to']}; gold in {d['gold_docs']}"
        for d in excluded
    ] or ["none"]
    text = "\n".join(lines) + "\n"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "tool_planning.md").write_text(text, encoding="utf-8")
    (RESULTS / "tool_planning.json").write_text(
        json.dumps({"labelled": rows, "golden": damage}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
