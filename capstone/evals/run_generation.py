# ruff: noqa: E501
"""Week 5 answer evaluation on the golden set: faithfulness, answer relevance, correctness.

Runs the real pipeline (`payments_rag.ask`: Azure hybrid search + semantic ranker, quote-verified
answerability check, cited answer or refusal) on every golden question, then asks a judge model
three things about each answer that was given:

* faithfulness: what share of its claims do the retrieved passages support?
* relevance: does it address the question asked?
* correctness: does it match the reference answer?

Refusals are scored separately: on questions the corpus cannot answer, refusing is right; on
answerable questions it is a false refusal (and counts as incorrect in the end-to-end number).

Limits: the judge is the same deployment that wrote the answers (gpt-4.1-mini), so its verdicts
are optimistic and imperfect; the reference answers and questions are mine; one run; no RAGAS or
Foundry evaluators (own judge prompts, unit-tested in payments_rag.answer_eval). Calls are paced
for the deployment's rate limit, and finished questions are cached in generation_cache.json so a
failed run resumes (delete the file for a fresh run).

    uv run --all-groups python capstone/evals/run_generation.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from typing import Any

from evaluate_chunking import HERE, META_SECTIONS, load_documents
from evaluate_grounding import (
    MAX_REQUESTS_PER_MINUTE,
    TPM_BUDGET,
    Pacer,
    call_with_retries,
    estimate_tokens,
)
from pydantic import BaseModel
from run_retrieval import RESULTS, load_golden

from payments_rag import (
    CORRECTNESS_SCORES,
    RELEVANCE_SCORES,
    AzureChatGenerator,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
    Hit,
    correctness_prompt,
    faithfulness_prompt,
    parse_faithfulness,
    parse_verdict,
    relevance_prompt,
    strip_sections,
)
from payments_rag.ask import STRATEGY, ask
from payments_rag.chunking import Chunk

FAITHFULNESS_TARGET = 0.9  # from capstone-architecture.md


class PacedChat(AzureChatGenerator):
    """The chat generator with rate-limit pacing and 429 retries; tracks time spent waiting."""

    def __init__(self, settings: AzureSettings, pacer: Pacer) -> None:
        super().__init__(settings)
        self._pacer = pacer
        self.waited = 0.0
        self.calls = 0  # model calls made, for cost comparisons

    def complete(
        self, prompt: str, *, json_mode: bool = False, schema: type[BaseModel] | None = None
    ) -> str:
        self.calls += 1
        started = time.monotonic()
        self._pacer.wait(estimate_tokens(prompt))
        self.waited += time.monotonic() - started
        return call_with_retries(
            lambda: super(PacedChat, self).complete(prompt, json_mode=json_mode, schema=schema)
        )


def to_hits(evidence: list[dict[str, str]]) -> tuple[Hit, ...]:
    return tuple(
        Hit(Chunk(e["text"], i, doc_id=e["doc_id"], section=e["section"]), 0.0)
        for i, e in enumerate(evidence)
    )


def mean(values: list[float]) -> float:
    defined = [v for v in values if not math.isnan(v)]
    return sum(defined) / len(defined) if defined else float("nan")


def pct(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.2f}"


def judge(chat: PacedChat, record: dict[str, Any], reference: str | None) -> dict[str, Any]:
    """Faithfulness, relevance and (when there is a reference) correctness for one given answer."""
    reply, question = record["reply"], record["question"]
    out: dict[str, Any] = {}
    faith = parse_faithfulness(
        chat.complete(faithfulness_prompt(reply, to_hits(record["evidence"])), json_mode=True)
    )
    out["faithfulness"] = (
        None
        if faith is None
        else {
            "score": None if math.isnan(faith.score) else faith.score,
            "supported": faith.supported,
            "total": faith.total,
            "unsupported": list(faith.unsupported),
        }
    )
    rel = parse_verdict(
        chat.complete(relevance_prompt(question, reply), json_mode=True), RELEVANCE_SCORES
    )
    out["relevance"] = None if rel is None else {"verdict": rel[0], "score": rel[1]}
    if reference:
        cor = parse_verdict(
            chat.complete(correctness_prompt(question, reference, reply), json_mode=True),
            CORRECTNESS_SCORES,
        )
        out["correctness"] = None if cor is None else {"verdict": cor[0], "score": cor[1]}
    return out


def run_question(chat: PacedChat, retriever: Any, q: dict[str, Any]) -> dict[str, Any]:
    waited_before = chat.waited
    started = time.monotonic()
    answer = ask(q["question"], retriever, chat)
    active_s = time.monotonic() - started - (chat.waited - waited_before)
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
        "seconds": round(active_s, 2),  # excludes time spent waiting for the rate limit
    }
    record["judgements"] = None if answer.refused else judge(chat, record, q["reference_answer"])
    return record


def summarise(records: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [r for r in records if r["expected"] == "answer"]
    refuse = [r for r in records if r["expected"] == "refuse"]
    given = [r for r in answerable if not r["refused"]]

    def scores(kind: str, rows: list[dict[str, Any]]) -> list[float]:
        out = []
        for r in rows:
            j = (r["judgements"] or {}).get(kind)
            if kind == "faithfulness":
                out.append(float("nan") if not j or j["score"] is None else j["score"])
            else:
                out.append(float("nan") if not j else j["score"])
        return out

    judge_failed = {
        kind: sum(1 for r in given if (r["judgements"] or {}).get(kind) is None)
        for kind in ("faithfulness", "relevance", "correctness")
    }
    seconds = sorted(r["seconds"] for r in records)
    p95 = (
        seconds[min(len(seconds) - 1, math.ceil(0.95 * len(seconds)) - 1)] if seconds else math.nan
    )
    return {
        "answerable": len(answerable),
        "answered": len(given),
        "false_refusals": len(answerable) - len(given),
        "faithfulness_mean": mean(scores("faithfulness", given)),
        "faithfulness_perfect": sum(1 for s in scores("faithfulness", given) if s == 1.0),
        "relevance_mean": mean(scores("relevance", given)),
        "correctness_mean_answered": mean(scores("correctness", given)),
        "correctness_end_to_end": mean(
            [
                0.0 if r["refused"] else s
                for r, s in zip(answerable, scores("correctness", answerable), strict=True)
            ]
        ),
        "correct_exact": sum(1 for s in scores("correctness", given) if s == 1.0),
        "to_refuse": len(refuse),
        "correctly_refused": sum(r["refused"] for r in refuse),
        "judge_failed": judge_failed,
        "seconds_median": statistics.median(seconds) if seconds else math.nan,
        "seconds_p95": p95,
    }


def render(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    by_split: dict[str, Any],
    semantic: bool = True,
) -> str:
    s = summary
    ranker = (
        "Azure hybrid + semantic ranker" if semantic else "Azure hybrid search, NO semantic ranker"
    )
    target = "meets" if s["faithfulness_mean"] >= FAITHFULNESS_TARGET else "is below"
    lines = [
        f"{len(records)} golden questions through the real pipeline ({ranker}, "
        "answerability check, cited answer). Judge = the same gpt-4.1-mini deployment, so scores are "
        "optimistic. One run. One question is worth "
        f"{1 / max(1, s['answerable']):.3f} of an answerable-question score.\n",
        "## Headline\n",
        "| Measure | Value |",
        "|---|---|",
        f"| Answerable questions answered | {s['answered']} of {s['answerable']} "
        f"({s['false_refusals']} false refusals) |",
        f"| Faithfulness (mean share of claims supported, answered only) | {pct(s['faithfulness_mean'])} "
        f"({s['faithfulness_perfect']} of {s['answered']} answers fully supported); "
        f"{target} the {FAITHFULNESS_TARGET} target |",
        f"| Answer relevance (answered only) | {pct(s['relevance_mean'])} |",
        f"| Correctness vs reference, answered only | {pct(s['correctness_mean_answered'])} "
        f"({s['correct_exact']} judged fully correct) |",
        f"| Correctness end to end (refusal counts as 0) | {pct(s['correctness_end_to_end'])} |",
        f"| Unanswerable questions correctly refused | {s['correctly_refused']} of {s['to_refuse']} |",
        f"| Latency per question, excluding rate-limit waits (median / p95) | "
        f"{s['seconds_median']:.1f} s / {s['seconds_p95']:.1f} s |",
        f"| Judge replies that could not be parsed | {s['judge_failed']} |",
        "",
        "## By question set (answerable questions)\n",
        "| Set | Answerable | Answered | Faithfulness | Relevance | Correct (answered) | Correct (end to end) |",
        "|---|---|---|---|---|---|---|",
    ]
    for split, v in by_split.items():
        lines.append(
            f"| {split} | {v['answerable']} | {v['answered']} | {pct(v['faithfulness_mean'])} "
            f"| {pct(v['relevance_mean'])} | {pct(v['correctness_mean_answered'])} "
            f"| {pct(v['correctness_end_to_end'])} |"
        )
    answerable = [r for r in records if r["expected"] == "answer"]
    flagged: list[str] = []
    for r in answerable:
        if r["refused"]:
            flagged.append(f"- {r['id']} FALSE REFUSAL ({r['reason']}): {r['question']}")
            continue
        j = r["judgements"] or {}
        cor = (j.get("correctness") or {}).get("verdict")
        faith = j.get("faithfulness") or {}
        if cor not in (None, "correct") or faith.get("unsupported"):
            detail = []
            if cor != "correct":
                detail.append(f"correctness={cor}")
            if faith.get("unsupported"):
                detail.append("unsupported: " + "; ".join(faith["unsupported"]))
            flagged.append(
                f"- {r['id']} ({', '.join(detail)}): {r['question']}\n  answer: {r['reply']}"
            )
    lines += [
        "",
        "## Answers to read by hand (not fully correct, not fully supported, or refused)\n",
    ]
    lines += flagged or ["none"]
    wrong = [r for r in records if r["expected"] == "refuse" and not r["refused"]]
    lines += ["", "## Unanswerable questions that got an answer\n"]
    lines += [f"- {r['id']}: {r['question']}\n  answer: {r['reply']}" for r in wrong] or ["none"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only the first N questions (smoke test)")
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="hybrid search without the semantic ranker (what the hosted API runs once the free "
        "allowance is used up); writes generation_no_semantic.* so the Week 5 results stay as they are",
    )
    args = parser.parse_args(argv)
    suffix = "_no_semantic" if args.no_semantic else ""
    cache_path = HERE / f"generation{suffix}_cache.json"
    sys.stdout.reconfigure(encoding="utf-8")  # answers contain characters such as the rupee sign

    documents = {d: strip_sections(t, META_SECTIONS) for d, t in load_documents().items()}
    golden = load_golden(documents)
    if args.limit:
        golden = golden[: args.limit]
    cache: dict[str, Any] = json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}

    settings = AzureSettings.from_env()
    chat = PacedChat(settings, Pacer(TPM_BUDGET, MAX_REQUESTS_PER_MINUTE))
    retriever = AzureHybridRetriever(
        AzureSearchStore(settings),
        AzureOpenAIEmbedder(settings),
        STRATEGY,
        semantic=not args.no_semantic,
    )
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
        record = run_question(chat, retriever, q)
        cache[q["id"]] = record
        records.append(record)
        cache_path.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
        status = "refused" if record["refused"] else "answered"
        print(f"[{n}/{len(golden)}] {q['id']} {status} ({record['seconds']} s)", flush=True)

    summary = summarise(records)
    splits = sorted({r["split"] for r in records if r["expected"] == "answer"})
    by_split = {
        split: summarise([r for r in records if r["split"] == split and r["expected"] == "answer"])
        for split in splits
    }
    text = render(records, summary, by_split, semantic=not args.no_semantic)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"generation{suffix}.md").write_text(text, encoding="utf-8")
    (RESULTS / f"generation{suffix}.json").write_text(
        json.dumps(
            {"summary": summary, "by_split": by_split, "records": records},
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
