"""Week 3: do XGBoost / LightGBM beat the Week 2 baseline? Same 5 folds as week2_cv.py.

Run from the repo root:  uv run python classical_ml/reports/week3_gbm.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "week3_gbm.md"

# Week 2 per-fold PR-AUC of the regularised HistGradientBoosting baseline (week2_cv.md).
WEEK2_BASELINE = np.array([0.848, 0.895, 0.871, 0.849, 0.830])


def candidates() -> dict[str, Any]:
    return {
        "XGBoost": xgb.XGBClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            min_child_weight=5,
            reg_lambda=10.0,
            subsample=0.8,
            colsample_bytree=0.8,
            tree_method="hist",
            n_jobs=-1,
            random_state=0,
        ),
        "LightGBM": lgb.LGBMClassifier(
            n_estimators=300,
            learning_rate=0.05,
            num_leaves=15,
            min_child_samples=50,
            reg_lambda=10.0,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            n_jobs=-1,
            random_state=0,
            verbose=-1,
        ),
        "HistGB (Week 2)": HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.05,
            l2_regularization=10.0,
            min_samples_leaf=100,
            early_stopping=False,
            random_state=0,
        ),
    }


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "raw" / "creditcard.csv")
    x, y = df.drop(columns="Class"), df["Class"]
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    scores: dict[str, list[float]] = {name: [] for name in candidates()}
    for i, (tr, te) in enumerate(folds.split(x, y), 1):
        for name, model in candidates().items():
            model.fit(x.iloc[tr], y.iloc[tr])
            scores[name].append(
                average_precision_score(y.iloc[te], model.predict_proba(x.iloc[te])[:, 1])
            )
        print(f"fold {i}:", {k: round(v[-1], 3) for k, v in scores.items()}, flush=True)

    lines = [
        "| Model | PR-AUC mean ± std | per fold | vs Week 2 (mean diff ± std, folds better) |",
        "|---|---|---|---|",
    ]
    for name, vals in scores.items():
        a = np.array(vals)
        d = a - WEEK2_BASELINE
        lines.append(
            f"| {name} | {a.mean():.3f} ± {a.std():.3f} | {' '.join(f'{v:.3f}' for v in a)} | "
            f"{d.mean():+.3f} ± {d.std():.3f}, {(d > 0).sum()}/5 |"
        )
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
