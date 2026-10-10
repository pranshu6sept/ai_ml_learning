# ruff: noqa: E501
"""Log an evaluation result file to MLflow, so runs can be compared over time.

    uv run --group tracking python capstone/evals/track_results.py results/generation_no_semantic.json

Reads a ``results/generation*.json`` written by ``run_generation.py`` (no model call, no Azure
needed) and records one MLflow run: the prompt version, the git commit, the source file name as
parameters; every number in the summary (plus the refusal share) as metrics; the JSON and the
Markdown report as artifacts.

Where it logs: ``MLFLOW_TRACKING_URI`` if set, otherwise a local SQLite file ``mlflow.db`` in the
repository root (git-ignored; MLflow 3 put its plain-folder store in maintenance mode). To log to the Azure ML workspace instead, set it to the workspace's MLflow URI
(``az ml workspace show --query mlflow_tracking_uri -o tsv``) and install ``azureml-mlflow``;
signing in with ``az login`` is enough, no key is needed.

Limits: this records what the results file says. It does not check the file was produced by the
current code (that is what the prompt-version check in ``eval_gate.py`` is for), and logging the same
file twice makes two runs.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_EXPERIMENT = "payments-rag-eval"
DEFAULT_STORE = f"sqlite:///{(HERE.parents[1] / 'mlflow.db').as_posix()}"


def metrics_from(summary: dict[str, Any]) -> dict[str, float]:
    """The numeric entries of an evaluation summary, plus the share of unanswerable ones refused."""
    out = {k: float(v) for k, v in summary.items() if isinstance(v, int | float)}
    to_refuse = float(summary.get("to_refuse", 0))
    if to_refuse:
        out["refused_share"] = float(summary.get("correctly_refused", 0)) / to_refuse
    return out


def params_from(data: dict[str, Any], source: Path, commit: str | None) -> dict[str, str]:
    params = {
        "source_file": source.name,
        "prompt_version": str(data.get("prompt_version", "unknown")),
        "semantic_ranker": "no" if "no_semantic" in source.name else "yes",
        "questions": str(len(data.get("records", []))),
    }
    if commit:
        params["git_commit"] = commit
    return params


def git_commit() -> str | None:
    """The short commit hash, with ``+dirty`` when the working tree has uncommitted changes."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    commit = head.stdout.strip()
    return (commit + ("+dirty" if status.stdout.strip() else "")) if commit else None


def log_results(path: Path, experiment: str = DEFAULT_EXPERIMENT) -> str:
    """Create one MLflow run from a results file; returns the run id."""
    import mlflow

    data = json.loads(path.read_text(encoding="utf-8"))
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI") or DEFAULT_STORE)
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=path.stem) as run:
        mlflow.log_params(params_from(data, path, git_commit()))
        mlflow.log_metrics(metrics_from(data["summary"]))
        mlflow.log_artifact(str(path))
        report = path.with_suffix(".md")
        if report.is_file():
            mlflow.log_artifact(str(report))
        return str(run.info.run_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("results", type=Path, help="a results/generation*.json file")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]  # MLflow prints an emoji
    path = args.results if args.results.is_absolute() else Path.cwd() / args.results
    if not path.is_file():
        path = HERE / args.results
    run_id = log_results(path, args.experiment)
    print(f"logged {path.name} as MLflow run {run_id} in experiment {args.experiment!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
