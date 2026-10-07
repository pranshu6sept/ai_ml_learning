# ruff: noqa: E501
"""Train the Week 3 fraud model (LightGBM) as an Azure ML job, and save it as an MLflow model.

    python train.py --data creditcard.csv --model-output ./model

Same data and settings as `classical_ml/reports/week3_gbm.py`: the credit-card fraud CSV and LightGBM with the
Week 3 hyperparameters. Differences, on purpose:
* it uses LightGBM's native API (`lgb.train`) instead of `LGBMClassifier`, because an MLflow-served native
  model returns the fraud probability, while the scikit-learn wrapper's MLflow scoring returns 0 or 1;
* it holds out a stratified test set (the Week 2 split helper) instead of cross-validating, because a deployed
  model is one fitted model, and the test numbers go to the run so the registered model carries its metrics.

Run as a job it logs the parameters and metrics to MLflow and writes the model to `--model-output`
(`mlflow` is imported only when needed, so the data and training functions can be tested without it).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(
    0, str(HERE.parent / "src")
)  # the job uploads classical_ml/, so the package is next to this file

from classical_ml.data import train_val_test_split  # noqa: E402

TARGET = "Class"
ROUNDS = 300
# Packages the managed endpoint's generated scoring script imports but MLflow does not put in the model's
# conda file. Without this the container started, failed to import `azureml.ai.monitoring`, and crashed in a
# loop (liveness probe 502) until the deployment timed out.
SERVING_EXTRAS = ["azureml-ai-monitoring"]
# The Week 3 LGBMClassifier settings, spelled in LightGBM's native parameter names.
PARAMS: dict[str, Any] = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 50,
    "lambda_l2": 10.0,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "feature_fraction": 0.8,
    "seed": 0,
    "verbosity": -1,
    "num_threads": 2,
}


def load(path: Path) -> pd.DataFrame:
    """The credit-card CSV; refuses a file without the label or with missing values."""
    df = pd.read_csv(path)
    if TARGET not in df.columns:
        raise ValueError(f"{path} has no {TARGET!r} column")
    if df.isna().any().any():
        raise ValueError(f"{path} has missing values")
    return df


def train(
    df: pd.DataFrame, rounds: int = ROUNDS, params: dict[str, Any] | None = None
) -> tuple[lgb.Booster, dict[str, float]]:
    """Fit on the train split; return the model and its test-set metrics."""
    train_df, val_df, test_df = train_val_test_split(df, TARGET)
    features = [c for c in df.columns if c != TARGET]
    booster = lgb.train(
        {**PARAMS, **(params or {})},
        lgb.Dataset(train_df[features], label=train_df[TARGET]),
        num_boost_round=rounds,
    )
    return booster, evaluate(booster, val_df, test_df, features)


def best_f1_threshold(y_true: np.ndarray, scores: np.ndarray) -> float:
    """The score cut-off with the best F1 on a set (chosen on validation, then applied to test)."""
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.argmax(f1))])


def evaluate(
    booster: lgb.Booster, val_df: pd.DataFrame, test_df: pd.DataFrame, features: list[str]
) -> dict[str, float]:
    val_scores = booster.predict(val_df[features])
    test_scores = booster.predict(test_df[features])
    y = test_df[TARGET].to_numpy()
    threshold = best_f1_threshold(val_df[TARGET].to_numpy(), val_scores)
    flagged = test_scores >= threshold
    tp = float(((flagged) & (y == 1)).sum())
    return {
        "test_pr_auc": float(average_precision_score(y, test_scores)),
        "test_roc_auc": float(roc_auc_score(y, test_scores)),
        "threshold_from_validation": threshold,
        "test_precision_at_threshold": tp / max(float(flagged.sum()), 1.0),
        "test_recall_at_threshold": tp / max(float((y == 1).sum()), 1.0),
        "test_rows": float(len(test_df)),
        "test_fraud_rows": float((y == 1).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, required=True, help="the creditcard.csv file")
    parser.add_argument(
        "--model-output", type=Path, required=True, help="folder to write the MLflow model to"
    )
    args = parser.parse_args()

    import mlflow
    import mlflow.lightgbm
    from mlflow.models import infer_signature

    df = load(args.data)
    booster, metrics = train(df)
    features = [c for c in df.columns if c != TARGET]
    sample = df[features].head(5)
    mlflow.log_params({**PARAMS, "rounds": ROUNDS, "rows": len(df)})
    mlflow.log_metrics(metrics)
    mlflow.lightgbm.save_model(
        booster,
        args.model_output,
        signature=infer_signature(sample, booster.predict(sample)),
        input_example=sample,
        extra_pip_requirements=SERVING_EXTRAS,
    )
    print({k: round(v, 4) for k, v in metrics.items()})


if __name__ == "__main__":
    main()
