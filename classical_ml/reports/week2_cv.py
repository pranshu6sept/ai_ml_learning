"""Week 2 follow-up: rank the four models with 5-fold cross-validation on all 492 frauds.

The single test split has only 74 frauds, so its ranking was noise (it even flipped relative to
validation). Here every fraud is scored once, out of fold, and the models are compared on the
*same* folds, so the differences are paired.

Run from the repo root:  uv run python classical_ml/reports/week2_cv.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from week2_metrics import DATA, models

OUT = Path(__file__).resolve().parent / "week2_cv.md"
N_SPLITS = 5


def main() -> None:
    df = pd.read_csv(DATA)
    x, y = df.drop(columns="Class"), df["Class"]
    folds = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)

    pr: dict[str, list[float]] = {name: [] for name in models()}
    roc: dict[str, list[float]] = {name: [] for name in models()}
    for fold, (train_idx, test_idx) in enumerate(folds.split(x, y), start=1):
        frauds = int(y.iloc[test_idx].sum())
        print(f"fold {fold}: {frauds} frauds held out", flush=True)
        for name, build in models().items():
            model = build().fit(x.iloc[train_idx], y.iloc[train_idx])
            p = model.predict_proba(x.iloc[test_idx])[:, 1]
            pr[name].append(average_precision_score(y.iloc[test_idx], p))
            roc[name].append(roc_auc_score(y.iloc[test_idx], p))
            print(f"  {name}: PR-AUC {pr[name][-1]:.3f}", flush=True)

    base = np.array(pr["Logistic regression"])
    lines = [
        f"{N_SPLITS}-fold stratified CV over all {len(df):,} transactions "
        f"({int(y.sum())} frauds, each scored once out of fold).\n",
        "| Model | PR-AUC mean ± std | per-fold PR-AUC | ROC-AUC mean | vs plain logistic "
        "(mean diff ± std, folds better) |",
        "|---|---|---|---|---|",
    ]
    for name, values in pr.items():
        arr = np.array(values)
        diff = arr - base
        versus = (
            "baseline"
            if name == "Logistic regression"
            else f"{diff.mean():+.3f} ± {diff.std():.3f}, {int((diff > 0).sum())}/{N_SPLITS}"
        )
        lines.append(
            f"| {name} | {arr.mean():.3f} ± {arr.std():.3f} | "
            f"{' '.join(f'{v:.3f}' for v in arr)} | {np.mean(roc[name]):.3f} | {versus} |"
        )
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
