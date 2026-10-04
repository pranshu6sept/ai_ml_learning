# ruff: noqa: E501
"""Cross-check the answers with Azure AI Foundry's evaluators (the `azure-ai-evaluation` package).

The same 58 answers that `run_generation.py` produced are graded by three ready-made Foundry
evaluators, using `gpt-5-mini` (not the model that wrote the answers) as the judge model:

* GroundednessEvaluator: is the answer grounded in the retrieved passages? (1 to 5)
* RelevanceEvaluator: does the answer address the question? (1 to 5)
* SimilarityEvaluator: how close is the answer to the reference answer? (1 to 5)

Nothing is regenerated: this reads `generation_cache.json`. It does not import `payments_rag`.

`azure-ai-evaluation` needs pandas < 3, which would downgrade this repo's pandas and could break
the Week 1-3 code, so it is NOT a project dependency. Run it in a throwaway environment:

    uv run --no-project --python 3.11 --with azure-ai-evaluation --with azure-identity \\
        python capstone/evals/run_foundry_check.py [--limit N]

Needs `az login` and `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_JUDGE_DEPLOYMENT` (read from `.env`).
Finished answers are cached in `foundry_check_cache.json`, so a failed run resumes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GENERATION_CACHE = HERE / "generation_cache.json"
CACHE = HERE / "foundry_check_cache.json"
RESULTS = HERE / "results"
API_VERSION = "2025-04-01-preview"
PASS_AT = 3  # Foundry's default threshold: 3 or more passes
KINDS = ("groundedness", "relevance", "similarity")


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip("'\"")
    return values


def with_retries(call: Any, attempts: int = 4) -> Any:
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - the SDK raises several types for 429 and 5xx
            if attempt == attempts - 1:
                raise
            wait = 20 * (attempt + 1)
            print(f"      error ({type(error).__name__}); waiting {wait} s", flush=True)
            time.sleep(wait)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only the first N answered questions")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator, SimilarityEvaluator
    from azure.identity import DefaultAzureCredential

    env = {**read_dotenv(ROOT / ".env"), **os.environ}
    config = {
        "azure_endpoint": env["AZURE_OPENAI_ENDPOINT"],
        "azure_deployment": env["AZURE_OPENAI_JUDGE_DEPLOYMENT"],
        "api_version": API_VERSION,
    }
    credential = DefaultAzureCredential()
    options = {"credential": credential, "is_reasoning_model": True}
    evaluators = {
        "groundedness": GroundednessEvaluator(config, **options),
        "relevance": RelevanceEvaluator(config, **options),
        "similarity": SimilarityEvaluator(config, **options),
    }

    records = [
        r for r in json.loads(GENERATION_CACHE.read_text("utf-8")).values() if not r["refused"]
    ]
    if args.limit:
        records = records[: args.limit]
    cache: dict[str, Any] = json.loads(CACHE.read_text("utf-8")) if CACHE.exists() else {}

    for n, r in enumerate(records, 1):
        cached = cache.get(r["id"])
        if (
            cached
            and cached["reply"] == r["reply"]
            and cached["judge"] == config["azure_deployment"]
        ):
            continue
        context = "\n\n".join(e["text"] for e in r["evidence"])
        out: dict[str, Any] = {}
        out["groundedness"] = with_retries(
            lambda r=r, context=context: evaluators["groundedness"](
                query=r["question"], response=r["reply"], context=context
            )
        )
        out["relevance"] = with_retries(
            lambda r=r: evaluators["relevance"](query=r["question"], response=r["reply"])
        )
        if r["reference_answer"]:
            out["similarity"] = with_retries(
                lambda r=r: evaluators["similarity"](
                    query=r["question"], response=r["reply"], ground_truth=r["reference_answer"]
                )
            )
        cache[r["id"]] = {"reply": r["reply"], "judge": config["azure_deployment"], "scores": out}
        CACHE.write_text(
            json.dumps(cache, indent=1, ensure_ascii=False, default=str), encoding="utf-8"
        )
        print(f"[{n}/{len(records)}] {r['id']} graded", flush=True)

    # Summaries over the answerable questions that got an answer (nu1 is an unanswerable one).
    scores: dict[str, dict[str, float]] = {k: {} for k in KINDS}
    for r in records:
        for kind in KINDS:
            item = cache[r["id"]]["scores"].get(kind)
            if item and isinstance(item.get(kind), int | float):
                scores[kind][r["id"]] = float(item[kind])
    mine_flagged = {
        "h05",
        "i04",
        "nu1",
    }  # answers one of my two judges marked as not fully supported
    ids = [r["id"] for r in records]
    lines = [
        f"{len(records)} answers from the generation run, graded by Azure AI Foundry evaluators (`azure-ai-evaluation`) with `{config['azure_deployment']}` "
        "as the judge model. Scores are 1 to 5; 3 or more passes (Foundry's default). One run.\n",
        "## Summary\n",
        "| Evaluator | Mean (1-5) | Pass rate (3+) | Scored 5 | Scored below 4 |",
        "|---|---|---|---|---|",
    ]
    for kind in KINDS:
        s = scores[kind]
        values = list(s.values())
        lines.append(
            f"| {kind} | {mean(values):.2f} | {sum(v >= PASS_AT for v in values)} of {len(values)} "
            f"| {sum(v == 5 for v in values)} | {sum(v < 4 for v in values)} |"
        )
    lines += [
        "",
        "## Answers scoring below 5 on groundedness, relevance or similarity (read by hand)\n",
    ]
    shown = 0
    by_id = {r["id"]: r for r in records}
    for i in ids:
        low = {k: scores[k][i] for k in KINDS if i in scores[k] and scores[k][i] < 5}
        if not low:
            continue
        shown += 1
        reasons = "; ".join(
            f"{k} {v:g}: {str(cache[i]['scores'][k].get(k + '_reason', ''))[:220]}"
            for k, v in low.items()
        )
        flag = " [also flagged by one of my judges]" if i in mine_flagged else ""
        lines.append(
            f"- {i}{flag}: {by_id[i]['question']}\n  answer: {by_id[i]['reply']}\n  {reasons}"
        )
    if not shown:
        lines.append("none")
    lines += [
        "",
        f"Answers my own judges flagged as not fully supported: {', '.join(sorted(mine_flagged & set(ids))) or 'none'}. "
        "Their Foundry groundedness scores: "
        + ", ".join(
            f"{i} = {scores['groundedness'].get(i, float('nan')):g}"
            for i in sorted(mine_flagged & set(ids))
        )
        + ".",
    ]
    text = "\n".join(lines) + "\n"
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "foundry_check.md").write_text(text, encoding="utf-8")
    (RESULTS / "foundry_check.json").write_text(
        json.dumps({k: scores[k] for k in KINDS}, indent=1), encoding="utf-8"
    )
    print(text)


if __name__ == "__main__":
    main()
