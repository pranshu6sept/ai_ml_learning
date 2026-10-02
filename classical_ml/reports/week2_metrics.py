"""Week 2 deliverable: compare imbalance strategies on the credit-card fraud data.

Protocol (so the table can be trusted):
  * every model is fitted on the training split only;
  * each model's alert threshold is chosen on the validation split (lowest expected cost);
  * the test split is scored once, at the end.

Run from the repo root:  uv run python classical_ml/reports/week2_metrics.py
Needs data/raw/creditcard.csv (see notes/week-02.md for how it was downloaded).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from classical_ml.data import train_val_test_split

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "raw" / "creditcard.csv"
OUT = Path(__file__).resolve().parent / "week2_metrics.md"

COST_MISSED_FRAUD = 500  # dollars lost when a fraud is not flagged
COST_FALSE_ALARM = 5  # dollars of reviewer time per wrongly flagged transaction
N_BOOTSTRAP = 200

Array = npt.NDArray[np.float64]


def best_threshold(y: pd.Series, scores: Array) -> float:
    """Score cut-off with the lowest expected cost on ``y``. Flag a row when score >= cut-off."""
    order = np.argsort(-scores)
    hits = y.to_numpy()[order]
    flagged_frauds = np.cumsum(hits)
    false_alarms = np.cumsum(1 - hits)
    missed = hits.sum() - flagged_frauds
    cost = COST_MISSED_FRAUD * missed + COST_FALSE_ALARM * false_alarms
    best = int(np.argmin(cost))
    if COST_MISSED_FRAUD * hits.sum() <= cost[best]:  # flagging nothing is cheapest
        return float("inf")
    return float(scores[order][best])


def operating_point(y: pd.Series, scores: Array, threshold: float) -> dict[str, float]:
    flagged = scores >= threshold
    caught = int((flagged & (y.to_numpy() == 1)).sum())
    false_alarms = int(flagged.sum()) - caught
    total_fraud = int(y.sum())
    return {
        "flagged": float(flagged.sum()),
        "precision": caught / flagged.sum() if flagged.sum() else float("nan"),
        "recall": caught / total_fraud,
        "cost": float(COST_MISSED_FRAUD * (total_fraud - caught) + COST_FALSE_ALARM * false_alarms),
    }


def bootstrap_pr_auc(y: pd.Series, scores: Array, seed: int = 0) -> tuple[float, float]:
    """95% interval for PR-AUC from resampling the test rows."""
    rng = np.random.default_rng(seed)
    y_arr = y.to_numpy()
    values = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, len(y_arr), size=len(y_arr))
        values.append(average_precision_score(y_arr[idx], scores[idx]))
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)


def models() -> dict[str, Callable[[], Any]]:
    def logistic(**kwargs: Any) -> LogisticRegression:
        return LogisticRegression(max_iter=1000, **kwargs)

    return {
        "Logistic regression": lambda: make_pipeline(StandardScaler(), logistic()),
        "Logistic + class weights": lambda: make_pipeline(
            StandardScaler(), logistic(class_weight="balanced")
        ),
        "Logistic + SMOTE": lambda: ImbPipeline(
            [("scale", StandardScaler()), ("smote", SMOTE(random_state=0)), ("model", logistic())]
        ),
        "Gradient boosting (regularised)": lambda: HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.05,
            l2_regularization=10.0,
            min_samples_leaf=100,
            early_stopping=False,
            random_state=0,
        ),
    }


def main() -> None:
    df = pd.read_csv(DATA)
    train, val, test = train_val_test_split(df, target="Class")
    x_train, y_train = train.drop(columns="Class"), train["Class"]
    x_val, y_val = val.drop(columns="Class"), val["Class"]
    x_test, y_test = test.drop(columns="Class"), test["Class"]

    rows = []
    for name, build in models().items():
        print(f"fitting {name} ...", flush=True)
        model = build().fit(x_train, y_train)
        p_val = model.predict_proba(x_val)[:, 1]
        p_test = model.predict_proba(x_test)[:, 1]
        threshold = best_threshold(y_val, p_val)
        point = operating_point(y_test, p_test, threshold)
        low, high = bootstrap_pr_auc(y_test, p_test)
        rows.append(
            {
                "Model": name,
                "PR-AUC (95% interval)": (
                    f"{average_precision_score(y_test, p_test):.3f} [{low:.3f}-{high:.3f}]"
                ),
                "ROC-AUC": f"{roc_auc_score(y_test, p_test):.3f}",
                "Val threshold": f"{threshold:.3f}",
                "Flagged": f"{point['flagged']:.0f}",
                "Precision": f"{point['precision']:.3f}",
                "Recall": f"{point['recall']:.3f}",
                "Cost ($)": f"{point['cost']:,.0f}",
            }
        )

    flag_nothing = COST_MISSED_FRAUD * int(y_test.sum())
    headers = list(rows[0])
    table = "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "|" + "|".join("---" for _ in headers) + "|",
            *("| " + " | ".join(row[h] for h in headers) + " |" for row in rows),
        ]
    )
    text = (
        f"Test split: {len(test):,} transactions, {int(y_test.sum())} frauds "
        f"({y_test.mean():.2%}).\n"
        f"Chance PR-AUC = fraud rate = {y_test.mean():.4f}. "
        f"Cost = ${COST_MISSED_FRAUD} per missed fraud + ${COST_FALSE_ALARM} per false alarm; "
        f"flagging nothing costs ${flag_nothing:,}.\n\n{table}\n"
    )
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
