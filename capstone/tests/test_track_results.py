# ruff: noqa: E501
"""Logging evaluation results to MLflow: the mapping is tested always, the real logging if installed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

EVALS = Path(__file__).resolve().parents[1] / "evals"
SUMMARY = {
    "answerable": 69,
    "answered": 51,
    "faithfulness_mean": 0.98,
    "correctly_refused": 25,
    "to_refuse": 26,
    "judge_failed": {"faithfulness": 0},  # a nested dict is not a metric
    "label": "text",  # nor is text
}


@pytest.fixture()
def tracker(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(str(EVALS))
    import track_results

    return track_results


def test_only_numbers_become_metrics_and_the_refusal_share_is_added(tracker: Any) -> None:
    metrics = tracker.metrics_from(SUMMARY)

    assert set(metrics) == {
        "answerable",
        "answered",
        "faithfulness_mean",
        "correctly_refused",
        "to_refuse",
        "refused_share",
    }
    assert metrics["refused_share"] == pytest.approx(25 / 26)


def test_no_refusal_share_when_nothing_was_to_be_refused(tracker: Any) -> None:
    assert "refused_share" not in tracker.metrics_from({"answered": 3})


def test_params_record_the_prompt_version_and_whether_the_ranker_was_on(tracker: Any) -> None:
    data = {"prompt_version": "abc123abc123", "records": [1, 2, 3]}

    off = tracker.params_from(data, Path("generation_no_semantic.json"), "deadbee")
    on = tracker.params_from(data, Path("generation.json"), None)

    assert off["semantic_ranker"] == "no" and on["semantic_ranker"] == "yes"
    assert off["prompt_version"] == "abc123abc123" and off["questions"] == "3"
    assert off["git_commit"] == "deadbee" and "git_commit" not in on
    assert tracker.params_from({}, Path("g.json"), None)["prompt_version"] == "unknown"


def test_a_results_file_is_logged_as_one_run(
    tracker: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mlflow = pytest.importorskip("mlflow")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    results = tmp_path / "generation_no_semantic.json"
    results.write_text(
        json.dumps({"prompt_version": "abc123abc123", "summary": SUMMARY, "records": []}),
        encoding="utf-8",
    )
    results.with_suffix(".md").write_text("report", encoding="utf-8")

    run_id = tracker.log_results(results, "test-experiment")

    run = mlflow.get_run(run_id)
    assert run.data.params["prompt_version"] == "abc123abc123"
    assert run.data.metrics["faithfulness_mean"] == pytest.approx(0.98)
    assert run.data.metrics["refused_share"] == pytest.approx(25 / 26)
    artifacts = {a.path for a in mlflow.MlflowClient().list_artifacts(run_id)}
    assert artifacts == {"generation_no_semantic.json", "generation_no_semantic.md"}
