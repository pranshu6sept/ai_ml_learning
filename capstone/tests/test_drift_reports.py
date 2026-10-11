"""The pure helpers behind the Week 11 drift reports (no Azure, no dataset)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def fraud_report() -> Any:
    pd = pytest.importorskip("pandas")
    pytest.importorskip("lightgbm")
    module = load(ROOT / "classical_ml" / "reports" / "week11_drift.py", "week11_drift")
    module.pd = pd
    return module


@pytest.fixture()
def query_report(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(str(ROOT / "capstone" / "evals"))
    return load(ROOT / "capstone" / "evals" / "run_drift.py", "run_drift")


def test_the_split_is_by_time_not_by_row_order(fraud_report: Any) -> None:
    import pandas as pd

    df = pd.DataFrame({"Time": [50, 10, 40, 20, 30, 60], "x": range(6)})

    first, second = fraud_report.split_by_time(df, 0.5)

    assert list(first["Time"]) == [10, 20, 30] and list(second["Time"]) == [40, 50, 60]
    assert first["Time"].max() < second["Time"].min()


def test_the_bootstrap_interval_brackets_the_metric_and_narrows_with_more_data(
    fraud_report: Any,
) -> None:
    rng = np.random.default_rng(0)

    def accuracy(y: np.ndarray, s: np.ndarray) -> float:
        return float(np.mean((s > 0.5) == y))

    def sample(n: int) -> tuple[np.ndarray, np.ndarray]:
        y = rng.integers(0, 2, n)
        s = np.where(rng.random(n) < 0.8, y, 1 - y).astype(float)
        return y, s

    small = sample(100)
    large = sample(5000)

    lo_s, hi_s = fraud_report.bootstrap_interval(*small, accuracy)
    lo_l, hi_l = fraud_report.bootstrap_interval(*large, accuracy)

    assert lo_s <= accuracy(*small) <= hi_s and lo_l <= accuracy(*large) <= hi_l
    assert (hi_l - lo_l) < (hi_s - lo_s)


def test_a_length_psi_is_read_against_what_the_same_size_gives_by_chance(query_report: Any) -> None:
    rng = np.random.default_rng(1)
    reference = list(rng.integers(30, 120, 48))

    same, same_null = query_report.length_psi_vs_null(reference, list(rng.integers(30, 120, 10)))
    longer, longer_null = query_report.length_psi_vs_null(
        reference, list(rng.integers(200, 400, 10))
    )

    assert same_null > 0.5  # tiny samples give a large PSI by chance alone
    assert same < same_null
    assert longer > longer_null


def test_the_null_auc_sits_near_or_below_chance(query_report: Any) -> None:
    pytest.importorskip("sklearn")
    rng = np.random.default_rng(2)
    reference = rng.normal(size=(48, 16))

    null = query_report.null_auc(reference, 12, draws=8)

    assert len(null) == 8 and max(null) < 0.9
