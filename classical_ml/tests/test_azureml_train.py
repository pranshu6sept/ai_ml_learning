import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

TRAIN = Path(__file__).resolve().parents[1] / "azureml" / "train.py"


@pytest.fixture(scope="module")
def train_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("azureml_train", TRAIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _transactions(n: int = 4000, fraud_rate: float = 0.02, seed: int = 0) -> pd.DataFrame:
    """A small imbalanced table where fraud shifts two of the features."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < fraud_rate).astype(int)
    frame = pd.DataFrame(rng.normal(size=(n, 4)), columns=["V1", "V2", "V3", "Amount"])
    frame["V1"] += y * 3.0
    frame["V2"] -= y * 2.0
    frame["Class"] = y
    return frame


def test_load_refuses_a_file_without_the_label(train_module, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "d.csv").write_text("V1,V2\n1,2\n")

    with pytest.raises(ValueError, match="Class"):
        train_module.load(tmp_path / "d.csv")


def test_load_refuses_missing_values(train_module, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "d.csv").write_text("V1,Class\n1,0\n,1\n")

    with pytest.raises(ValueError, match="missing values"):
        train_module.load(tmp_path / "d.csv")


def test_training_finds_the_planted_signal_and_reports_honest_test_metrics(train_module) -> None:  # type: ignore[no-untyped-def]
    booster, metrics = train_module.train(_transactions(), rounds=60)

    assert metrics["test_roc_auc"] > 0.95
    assert metrics["test_pr_auc"] > 0.5
    assert 0.0 <= metrics["test_precision_at_threshold"] <= 1.0
    assert 0.0 <= metrics["test_recall_at_threshold"] <= 1.0
    assert metrics["test_rows"] == 600.0  # 15% of 4000, stratified
    assert booster.num_trees() == 60


def test_the_model_returns_probabilities_not_labels(train_module) -> None:  # type: ignore[no-untyped-def]
    df = _transactions()
    booster, _ = train_module.train(df, rounds=30)

    scores = booster.predict(df.drop(columns="Class").head(50))

    assert ((scores >= 0) & (scores <= 1)).all()
    assert len(set(np.round(scores, 6))) > 2  # a spread of probabilities, not 0 and 1


def test_best_f1_threshold_separates_a_clean_split(train_module) -> None:  # type: ignore[no-untyped-def]
    y = np.array([0, 0, 0, 0, 1, 1])
    scores = np.array([0.05, 0.1, 0.2, 0.3, 0.8, 0.9])

    threshold = train_module.best_f1_threshold(y, scores)

    assert 0.3 < threshold <= 0.8


def test_the_serving_extras_include_the_package_the_endpoint_script_imports(train_module) -> None:  # type: ignore[no-untyped-def]
    assert "azureml-ai-monitoring" in train_module.SERVING_EXTRAS


def test_week_3_hyperparameters_are_preserved(train_module) -> None:  # type: ignore[no-untyped-def]
    p = train_module.PARAMS

    assert (p["learning_rate"], p["num_leaves"], p["min_data_in_leaf"], p["lambda_l2"]) == (
        0.05,
        15,
        50,
        10.0,
    )
    assert train_module.ROUNDS == 300
