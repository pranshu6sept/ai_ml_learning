# ruff: noqa: E501
"""Week 11: has the fraud data drifted between the first and second day, and did the Week 3 model notice?

    uv run python classical_ml/reports/week11_drift.py

Time-orders the credit-card transactions and splits them in half: the first half is the "reference" the
model is built on, the second half is "current". Then:

1. **Feature drift**: PSI and the KS statistic for each of the 29 features (V1..V28, Amount), reference
   against current. (`Time` is excluded: it drifts by construction.)
2. **Score drift**: a LightGBM model with the Week 3 settings is trained on 80% of the reference and the
   shape of its scores on held-out reference rows is compared with the shape on current rows.
3. **Quality decay**: PR-AUC on held-out reference rows against PR-AUC on current rows, each with a 95%
   bootstrap interval, because fraud is rare (0.17% of rows) and a quality number built on a few hundred
   cases moves a lot by chance.

Limits: two days of data from one European card issuer's 2013 transactions (features are anonymised PCA
components); there is no real production traffic here, so "drift" means "the second day differs from
the first", not "the world changed". Fraud counts per half are small. The cut-offs for PSI are rules of
thumb.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "capstone" / "src"))
sys.path.insert(0, str(ROOT / "classical_ml" / "src"))

from payments_rag.drift import drift_table, ks_2samp, psi, quality_decay  # noqa: E402

DATA = ROOT / "data" / "raw" / "creditcard.csv"
TARGET = "Class"
FEATURES = [f"V{i}" for i in range(1, 29)] + ["Amount"]
BOOTSTRAPS = 300


def week3_params() -> tuple[dict[str, Any], int]:
    """The LightGBM settings of the Azure ML training script (the Week 3 model), read from its file."""
    spec = importlib.util.spec_from_file_location(
        "train_script", ROOT / "classical_ml" / "azureml" / "train.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.PARAMS), int(module.ROUNDS)


def split_by_time(df: pd.DataFrame, share: float = 0.5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The earliest ``share`` of rows (by ``Time``) and the rest."""
    ordered = df.sort_values("Time", kind="stable").reset_index(drop=True)
    cut = int(len(ordered) * share)
    return ordered.iloc[:cut], ordered.iloc[cut:]


def bootstrap_interval(
    y: np.ndarray, scores: np.ndarray, metric: Any, draws: int = BOOTSTRAPS, seed: int = 0
) -> tuple[float, float]:
    """95% percentile bootstrap interval of ``metric(y, scores)`` (resampling rows)."""
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(draws):
        pick = rng.integers(0, len(y), len(y))
        if y[pick].sum() == 0:
            continue
        values.append(metric(y[pick], scores[pick]))
    low, high = np.percentile(values, [2.5, 97.5])
    return float(low), float(high)


def analyse(df: pd.DataFrame, rounds: int | None = None) -> dict[str, Any]:
    params, default_rounds = week3_params()
    ref, cur = split_by_time(df)
    features = {name: (ref[name].to_numpy(), cur[name].to_numpy()) for name in FEATURES}
    table = drift_table(features)

    # Control: two random halves of the same data. Nothing has drifted between them, so any
    # detector that fires here is firing on noise.
    shuffled = df.sample(frac=1.0, random_state=0).reset_index(drop=True)
    half = len(shuffled) // 2
    control = drift_table(
        {
            name: (shuffled[name].iloc[:half].to_numpy(), shuffled[name].iloc[half:].to_numpy())
            for name in FEATURES
        }
    )

    train, held = train_test_split(ref, test_size=0.2, stratify=ref[TARGET], random_state=0)
    booster = lgb.train(
        params,
        lgb.Dataset(train[FEATURES], label=train[TARGET]),
        num_boost_round=rounds or default_rounds,
    )
    held_scores = booster.predict(held[FEATURES])
    cur_scores = booster.predict(cur[FEATURES])
    # Scores are extreme (near 0 or 1), so compare them on the log-odds scale.
    logit = lambda p: np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))  # noqa: E731
    score_psi = psi(logit(held_scores), logit(cur_scores))
    score_ks, score_p = ks_2samp(logit(held_scores), logit(cur_scores))

    y_held, y_cur = held[TARGET].to_numpy(), cur[TARGET].to_numpy()
    pr = {
        "reference_holdout": float(average_precision_score(y_held, held_scores)),
        "current": float(average_precision_score(y_cur, cur_scores)),
    }
    pr_ci = {
        "reference_holdout": bootstrap_interval(y_held, held_scores, average_precision_score),
        "current": bootstrap_interval(y_cur, cur_scores, average_precision_score),
    }
    roc = {
        "reference_holdout": float(roc_auc_score(y_held, held_scores)),
        "current": float(roc_auc_score(y_cur, cur_scores)),
    }
    # The tolerance is the width of the noisier interval's half, so a drop inside it is not called decay.
    half_width = max((hi - lo) / 2 for lo, hi in pr_ci.values())
    return {
        "rows": {"reference": len(ref), "current": len(cur)},
        "fraud": {"reference": int(ref[TARGET].sum()), "current": int(cur[TARGET].sum())},
        "features": [row.__dict__ for row in table],
        "control": [row.__dict__ for row in control],
        "score": {"psi": score_psi, "ks": score_ks, "ks_p": score_p},
        "pr_auc": pr,
        "pr_auc_95ci": pr_ci,
        "roc_auc": roc,
        "decay": quality_decay(pr["reference_holdout"], pr["current"], half_width).__dict__,
        "tolerance_used": half_width,
    }


def render(r: dict[str, Any]) -> str:
    lines = [
        "# Week 11: drift in the fraud data between day 1 and day 2\n",
        f"Reference = the first {r['rows']['reference']:,} transactions by time ({r['fraud']['reference']} fraud); "
        f"current = the next {r['rows']['current']:,} ({r['fraud']['current']} fraud). Model = the Week 3 LightGBM settings, "
        "trained on 80% of the reference. One run; no production traffic exists, so this shows what the detectors report on real "
        "data, not that the world changed.\n",
        "## Feature drift (top 10 by PSI of 29)\n",
        "| Feature | PSI | Verdict | KS gap | KS p-value |",
        "|---|---|---|---|---|",
    ]
    for row in r["features"][:10]:
        lines.append(
            f"| {row['name']} | {row['psi']:.3f} | {row['verdict']} | {row['ks']:.3f} | {row['p_value']:.1e} |"
        )
    counts: dict[str, int] = {}
    for row in r["features"]:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    lines += [
        "",
        f"Across all 29 features: {counts.get('stable', 0)} stable, {counts.get('moderate', 0)} moderate, {counts.get('major', 0)} major (PSI cut-offs 0.1 and 0.25).\n",
        "**Control** (two random halves of the same data, where nothing can have drifted): "
        f"{sum(c['verdict'] == 'stable' for c in r['control'])} of 29 features stable, largest PSI "
        f"{max(c['psi'] for c in r['control']):.4f}, largest KS gap "
        f"{max(c['ks'] for c in r['control']):.4f}. The detectors are quiet when nothing has moved, "
        "so the shifts above are real differences between the two days (why the days differ was "
        "not investigated).\n",
        "## Does the model's output look different?\n",
        f"Score distribution (log-odds), held-out reference vs current: PSI {r['score']['psi']:.3f}, KS gap {r['score']['ks']:.3f} (p {r['score']['ks_p']:.1e}).\n",
        "## Did quality fall?\n",
        "| | Reference hold-out | Current |",
        "|---|---|---|",
        f"| PR-AUC | {r['pr_auc']['reference_holdout']:.3f} (95% interval {r['pr_auc_95ci']['reference_holdout'][0]:.3f} to {r['pr_auc_95ci']['reference_holdout'][1]:.3f}) | {r['pr_auc']['current']:.3f} ({r['pr_auc_95ci']['current'][0]:.3f} to {r['pr_auc_95ci']['current'][1]:.3f}) |",
        f"| ROC-AUC | {r['roc_auc']['reference_holdout']:.3f} | {r['roc_auc']['current']:.3f} |",
        "",
        f"Drop in PR-AUC {r['decay']['drop']:+.3f}; tolerance (half the wider bootstrap interval) {r['tolerance_used']:.3f}; "
        f"flagged as decay: **{r['decay']['flagged']}**.\n",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    df = pd.read_csv(DATA)
    result = analyse(df)
    text = render(result)
    out = ROOT / "classical_ml" / "reports"
    (out / "week11_drift.md").write_text(text, encoding="utf-8")
    (out / "week11_drift.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
