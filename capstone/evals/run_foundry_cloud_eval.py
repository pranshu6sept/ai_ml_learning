# ruff: noqa: E501
"""Run Foundry's built-in evaluators inside the Foundry project (a cloud evaluation).

Week 5 ran the same evaluator definitions locally (`run_foundry_check.py`, the `azure-ai-evaluation` package).
Here the 57 answers from `generation_cache.json` are sent to the project, where the service runs the evaluators
with the project's own judge deployment and stores the run, so it appears in the Foundry portal with a report
URL. Evaluators: groundedness (query, response, context), relevance (query, response), similarity (query,
response, ground truth). Judge: `gpt-5-mini` on the Foundry resource.

`azure-ai-projects` is not a project dependency (it pulls its own `openai` pin). Run in a throwaway environment:

    uv run --no-project --python 3.11 --with "azure-ai-projects>=2.2.0" --with azure-identity \\
        python capstone/evals/run_foundry_cloud_eval.py [--limit N]

Needs `az login`, the Foundry User role on the Foundry resource, AZURE_W7_FOUNDRY_PROJECT_ENDPOINT in `.env`.
Writes `results/foundry_cloud_eval.md|json`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / "results"
JUDGE = "gpt-5-mini"
CRITERIA = (
    (
        "groundedness",
        "builtin.groundedness",
        {"query": "{{item.query}}", "response": "{{item.response}}", "context": "{{item.context}}"},
    ),
    (
        "relevance",
        "builtin.relevance",
        {"query": "{{item.query}}", "response": "{{item.response}}"},
    ),
    (
        "similarity",
        "builtin.similarity",
        {
            "query": "{{item.query}}",
            "response": "{{item.response}}",
            "ground_truth": "{{item.ground_truth}}",
        },
    ),
)


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip("'\"")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only the first N answers")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import TestingCriterionAzureAIEvaluator
    from azure.identity import DefaultAzureCredential
    from openai.types.eval_create_params import DataSourceConfigCustom
    from openai.types.evals.create_eval_jsonl_run_data_source_param import (
        CreateEvalJSONLRunDataSourceParam,
        SourceFileContent,
        SourceFileContentContent,
    )

    endpoint = {**read_dotenv(ROOT / ".env"), **os.environ}["AZURE_W7_FOUNDRY_PROJECT_ENDPOINT"]
    records = [
        r
        for r in json.loads((HERE / "generation_cache.json").read_text("utf-8")).values()
        if not r["refused"] and r["reference_answer"]
    ]
    if args.limit:
        records = records[: args.limit]
    items = [
        {
            "id": r["id"],
            "query": r["question"],
            "response": r["reply"],
            "context": "\n\n".join(f"[{n}] {e['text']}" for n, e in enumerate(r["evidence"], 1)),
            "ground_truth": r["reference_answer"],
        }
        for r in records
    ]

    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    openai_client = client.get_openai_client()

    schema = {
        "type": "object",
        "properties": {
            k: {"type": "string"} for k in ("id", "query", "response", "context", "ground_truth")
        },
        "required": ["id", "query", "response", "context", "ground_truth"],
    }
    criteria = [
        TestingCriterionAzureAIEvaluator(
            type="azure_ai_evaluator",
            name=name,
            evaluator_name=evaluator,
            initialization_parameters={"model": JUDGE},
            data_mapping=mapping,
        )
        for name, evaluator, mapping in CRITERIA
    ]
    evaluation = openai_client.evals.create(
        name="payments-rag answers (week 7)",
        data_source_config=DataSourceConfigCustom(type="custom", item_schema=schema),
        testing_criteria=criteria,
    )
    run = openai_client.evals.runs.create(
        eval_id=evaluation.id,
        name=f"golden answers x {len(items)}",
        data_source=CreateEvalJSONLRunDataSourceParam(
            type="jsonl",
            source=SourceFileContent(
                type="file_content", content=[SourceFileContentContent(item=i) for i in items]
            ),
        ),
    )
    print(f"eval {evaluation.id}, run {run.id}: waiting ...", flush=True)
    started = time.monotonic()
    while True:
        run = openai_client.evals.runs.retrieve(run_id=run.id, eval_id=evaluation.id)
        if run.status in ("completed", "failed", "canceled"):
            break
        if time.monotonic() - started > 1500:
            openai_client.evals.runs.cancel(run_id=run.id, eval_id=evaluation.id)
            raise TimeoutError("cloud evaluation did not finish in 25 minutes; cancelled")
        time.sleep(10)
    if run.status != "completed":
        raise RuntimeError(f"run ended in {run.status}: {getattr(run, 'error', None)}")

    rows = [
        i.to_dict()
        for i in openai_client.evals.runs.output_items.list(run_id=run.id, eval_id=evaluation.id)
    ]
    run_dict = run.to_dict()

    scores: dict[str, dict[str, float]] = {name: {} for name, _e, _m in CRITERIA}
    passed: dict[str, int] = dict.fromkeys(scores, 0)
    for row in rows:
        item_id = (row.get("datasource_item") or {}).get("id")
        for res in row.get("results") or []:
            name = str(res.get("name", "")).lower()
            if name in scores and res.get("score") is not None and item_id:
                scores[name][item_id] = float(res["score"])
                passed[name] += int(bool(res.get("passed")))

    local = (
        json.loads((RESULTS / "foundry_check.json").read_text("utf-8"))
        if (RESULTS / "foundry_check.json").exists()
        else {}
    )

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else float("nan")

    lines = [
        f"{len(items)} answers (the answered, answerable golden questions) evaluated inside the Foundry project by the built-in evaluators, judge `{JUDGE}` on the Foundry resource. "
        f"Run status `{run.status}`; report: {getattr(run, 'report_url', None)}\n",
        "| Evaluator | Scored | Mean (1-5) | Passed (3+) | Scored 5 | Same evaluator run locally in Week 5: mean |",
        "|---|---|---|---|---|---|",
    ]
    for name, by_id in scores.items():
        vals = list(by_id.values())
        local_vals = [
            v for k, v in (local.get(name) or {}).items() if k in {i["id"] for i in items}
        ]
        lines.append(
            f"| {name} | {len(vals)} | {mean(vals):.2f} | {passed[name]} of {len(vals)} | {sum(v == 5 for v in vals)} | {mean(local_vals):.2f} (n={len(local_vals)}) |"
        )
    low = sorted((i, name, s) for name, d in scores.items() for i, s in d.items() if s < 4)
    lines += ["", "## Answers scoring below 4 (read by hand)\n"] + (
        [f"- {i}: {name} {s:g}" for i, name, s in low] or ["none"]
    )
    counts = run_dict.get("result_counts")
    lines += ["", f"Run result counts reported by the service: {counts}", ""]
    text = "\n".join(lines)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "foundry_cloud_eval.md").write_text(text, encoding="utf-8")
    (RESULTS / "foundry_cloud_eval.json").write_text(
        json.dumps({"run": run_dict, "scores": scores, "n": len(items)}, indent=1, default=str),
        encoding="utf-8",
    )
    print(text)


if __name__ == "__main__":
    main()
