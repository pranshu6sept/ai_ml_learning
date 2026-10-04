# ruff: noqa: E501
"""Week 6 evaluation: the LangGraph pipeline on the golden set, compared with the plain `ask` pipeline.

Same 95 golden questions, same judge (gpt-4.1-mini, the answering model, so scores are optimistic),
same metrics as `run_generation.py`, plus what the graph adds: which path each question took, how
often it rewrote the search or regenerated the answer, how many model calls it spent, and whether the
router wrongly declined an in-scope question.

    uv run --all-groups python capstone/evals/run_graph.py [--limit N]

Finished questions are cached in `graph_cache.json` (delete it for a fresh run). Writes
`results/graph.md` and `results/graph.json`. Needs `az login`, the deployed resources and the
`orchestration` dependency group.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from typing import Any

from evaluate_chunking import HERE, META_SECTIONS, load_documents
from evaluate_grounding import Pacer
from run_generation import PacedChat, judge, pct, summarise
from run_retrieval import RESULTS, load_golden

from payments_rag import (
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    strip_sections,
)
from payments_rag.ask import STRATEGY
from payments_rag.graph import Deps, build_graph, run_graph

CACHE = HERE / "graph_cache.json"
TPM_BUDGET = 35000  # the chat deployment allows 50,000 tokens per minute
MAX_REQUESTS_PER_MINUTE = 30  # the chat deployment allows 50 requests per minute; leave headroom


def run_question(chat: PacedChat, graph: Any, q: dict[str, Any]) -> dict[str, Any]:
    calls_before, waited_before = chat.calls, chat.waited
    started = time.monotonic()
    result = run_graph(graph, q["question"], thread_id=None)
    active_s = time.monotonic() - started - (chat.waited - waited_before)
    answer = result.answer
    record: dict[str, Any] = {
        "id": q["id"],
        "split": q["split"],
        "expected": q["expected"],
        "question": q["question"],
        "reference_answer": q["reference_answer"],
        "reply": answer.text,
        "refused": answer.refused,
        "reason": answer.reason,
        "sources": list(answer.sources),
        "evidence": [
            {"doc_id": h.chunk.doc_id, "section": h.chunk.section, "text": h.chunk.text}
            for h in answer.evidence
        ],
        "trace": list(result.trace),
        "llm_calls": chat.calls - calls_before,
        "seconds": round(active_s, 2),
    }
    # Chit chat and declines are not answers from the passages, so they are not judged for them.
    judged = not answer.refused and bool(answer.evidence)
    record["judgements"] = judge(chat, record, q["reference_answer"]) if judged else None
    return record


def path_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    traces = [r["trace"] for r in records]
    declined = [r for r in records if "decline" in r["trace"]]
    return {
        "rewrote_search": sum("rewrite" in t for t in traces),
        "regenerated_answer": sum("regenerate" in t for t in traces),
        "declined_out_of_scope": len(declined),
        "declined_but_answerable": [r["id"] for r in declined if r["expected"] == "answer"],
        "small_talk": sum("small_talk" in t for t in traces),
        "validation_failures": sum(
            any(step.startswith("validate:fail") for step in t) for t in traces
        ),
        "mean_llm_calls": sum(r["llm_calls"] for r in records) / max(1, len(records)),
    }


def render(
    records: list[dict[str, Any]],
    s: dict[str, Any],
    paths: dict[str, Any],
    ask_s: dict[str, Any] | None,
) -> str:
    def col(key: str, fmt: str = "{:.2f}") -> str:
        return "n/a" if ask_s is None else fmt.format(ask_s[key])

    rows = [
        (
            "Answerable questions answered",
            f"{ask_s['answered']} of {ask_s['answerable']}" if ask_s else "n/a",
            f"{s['answered']} of {s['answerable']}",
        ),
        (
            "False refusals",
            str(ask_s["false_refusals"]) if ask_s else "n/a",
            str(s["false_refusals"]),
        ),
        ("Faithfulness (answered)", col("faithfulness_mean"), pct(s["faithfulness_mean"])),
        ("Answer relevance (answered)", col("relevance_mean"), pct(s["relevance_mean"])),
        (
            "Correctness vs reference (answered)",
            col("correctness_mean_answered"),
            pct(s["correctness_mean_answered"]),
        ),
        ("Correctness end to end", col("correctness_end_to_end"), pct(s["correctness_end_to_end"])),
        (
            "Unanswerable correctly refused",
            f"{ask_s['correctly_refused']} of {ask_s['to_refuse']}" if ask_s else "n/a",
            f"{s['correctly_refused']} of {s['to_refuse']}",
        ),
        (
            "Latency median / p95 (s, excl. rate-limit waits)",
            f"{ask_s['seconds_median']:.1f} / {ask_s['seconds_p95']:.1f}" if ask_s else "n/a",
            f"{s['seconds_median']:.1f} / {s['seconds_p95']:.1f}",
        ),
    ]
    lines = [
        f"{len(records)} golden questions through the LangGraph pipeline (route, retrieve, grade, optional rewrite, generate with a Pydantic schema, validate) "
        "versus the plain `ask` pipeline from Week 5. Same retrieval (Azure hybrid + semantic ranker), same answering model, same judge (gpt-4.1-mini, "
        "so scores are optimistic). One run.\n",
        "## Graph vs plain pipeline\n",
        "| Measure | Plain `ask` | Graph |",
        "|---|---|---|",
        *[f"| {a} | {b} | {c} |" for a, b, c in rows],
        "",
        "## What the graph did\n",
        "| Event | Count |",
        "|---|---|",
        f"| Search rewritten once after weak evidence | {paths['rewrote_search']} |",
        f"| Answer regenerated after failing validation | {paths['regenerated_answer']} |",
        f"| Validation failures (first draft) | {paths['validation_failures']} |",
        f"| Declined by the router as out of scope | {paths['declined_out_of_scope']} |",
        f"| In-scope answerable questions the router declined | {len(paths['declined_but_answerable'])} {paths['declined_but_answerable'] or ''} |",
        f"| Small talk | {paths['small_talk']} |",
        f"| Model calls per question (excluding the judge) | {paths['mean_llm_calls']:.1f} |",
        "",
        "## Paths taken\n",
        "| Path | Questions |",
        "|---|---|",
    ]
    shapes = Counter(" > ".join(step.split(" (")[0] for step in r["trace"]) for r in records)
    lines += [f"| {shape} | {n} |" for shape, n in shapes.most_common()]
    answerable = [r for r in records if r["expected"] == "answer"]
    lines += [
        "",
        "## By question set (answerable questions)\n",
        "| Set | Answerable | Answered | Faithfulness | Correct (answered) | Correct (end to end) |",
        "|---|---|---|---|---|---|",
    ]
    for split in sorted({r["split"] for r in answerable}):
        v = summarise([r for r in answerable if r["split"] == split])
        lines.append(
            f"| {split} | {v['answerable']} | {v['answered']} | {pct(v['faithfulness_mean'])} "
            f"| {pct(v['correctness_mean_answered'])} | {pct(v['correctness_end_to_end'])} |"
        )
    flagged = []
    for r in answerable:
        if r["refused"]:
            flagged.append(
                f"- {r['id']} FALSE REFUSAL ({r['reason']}; path {' > '.join(r['trace'])}): {r['question']}"
            )
    lines += ["", "## False refusals (read by hand)\n"] + (flagged or ["none"])
    wrong = [r for r in records if r["expected"] == "refuse" and not r["refused"]]
    lines += ["", "## Unanswerable questions that got an answer\n"]
    lines += [f"- {r['id']}: {r['question']}\n  answer: {r['reply']}" for r in wrong] or ["none"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only the first N questions (smoke test)")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = load_golden(documents)
    if args.limit:
        golden = golden[: args.limit]
    cache: dict[str, Any] = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}

    settings = AzureSettings.from_env()
    chat = PacedChat(settings, Pacer(TPM_BUDGET, MAX_REQUESTS_PER_MINUTE))
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings), AzureOpenAIEmbedder(settings), STRATEGY, semantic=True
    )
    graph = build_graph(Deps(retriever, chat))  # type: ignore[arg-type]
    records = []
    for n, q in enumerate(golden, 1):
        cached = cache.get(q["id"])
        if (
            cached
            and cached["question"] == q["question"]
            and cached["reference_answer"] == q["reference_answer"]
        ):
            records.append(cached)
            continue
        record = run_question(chat, graph, q)
        cache[q["id"]] = record
        records.append(record)
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        print(
            f"[{n}/{len(golden)}] {q['id']} {' > '.join(record['trace'])} ({record['seconds']} s)",
            flush=True,
        )

    summary = summarise(records)
    paths = path_stats(records)
    generation = RESULTS / "generation.json"
    ask_summary = (
        json.loads(generation.read_text("utf-8"))["summary"] if generation.exists() else None
    )
    text = render(records, summary, paths, ask_summary)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "graph.md").write_text(text, encoding="utf-8")
    (RESULTS / "graph.json").write_text(
        json.dumps(
            {"summary": summary, "paths": paths, "records": records}, indent=1, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
