"""Drift statistics: has the data a model sees today moved away from the data it was built on?

    psi(reference, current)            # Population Stability Index of one numeric feature
    ks_2samp(reference, current)       # two-sample Kolmogorov-Smirnov statistic and p-value
    embedding_drift(ref_vectors, cur_vectors)   # centroid distance, and a classifier AUC
    drift_table({"feature": (ref, cur), ...})   # one row per feature, with a verdict
    quality_decay(baseline, current)   # did a quality metric fall by more than noise?

Written with numpy only (SciPy's ``ks_2samp`` is used in the tests as a cross-check), so it can
run anywhere the package does. What these numbers mean, and do not mean:

* **PSI** compares the share of data in each bin (equal-frequency bins of the *reference*). The
  usual reading is below 0.1 stable, 0.1 to 0.25 moderate shift, above 0.25 major shift. Those
  cut-offs are an industry rule of thumb, not a statistical test; PSI also grows when either
  sample is small, so it is noisy below a few hundred rows.
* **KS** is the largest gap between the two cumulative distributions. Its p-value says whether
  the gap is bigger than chance, which with a huge sample is almost always true for any real
  difference; read the statistic (the size of the gap) before the p-value.
* **Embedding drift** has two views: the cosine distance between the two centroids (a shift in
  the average meaning) and a classifier's cross-validated AUC at telling reference from current
  (0.5 means it cannot; near 1.0 means they are easy to separate). The classifier catches changes
  of spread and shape that a centroid misses.
* Drift is a signal to look, not proof that quality fell. A shift in inputs can be harmless, and
  quality can fall with no input drift (for example when the corpus changes); ``quality_decay``
  watches quality directly for that reason.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

PSI_STABLE = 0.1
PSI_MAJOR = 0.25
Array = npt.NDArray[np.float64]


def _clean(values: Sequence[float] | Array) -> Array:
    array = np.asarray(values, dtype=np.float64).ravel()
    return array[np.isfinite(array)]


def psi(
    reference: Sequence[float] | Array,
    current: Sequence[float] | Array,
    bins: int = 10,
    floor: float = 1e-4,
) -> float:
    """Population Stability Index of ``current`` against ``reference``.

    Bin edges are quantiles of the reference, so each reference bin holds about the same share;
    the first and last bins are open-ended, so values outside the reference range still count.
    Empty bins are floored at ``floor`` so the logarithm is defined.
    """
    ref, cur = _clean(reference), _clean(current)
    if len(ref) == 0 or len(cur) == 0:
        raise ValueError("both samples need at least one finite value")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)[1:-1]))
    # side="left": a value equal to an edge goes in the lower bin, the (a, b] convention. With
    # "right", a constant reference feature (all edges equal) put every later value in the same
    # bin as itself, so a column that was always 1 and became 2 scored a PSI of 0.
    ref_share = np.bincount(np.searchsorted(edges, ref, side="left"), minlength=len(edges) + 1)
    cur_share = np.bincount(np.searchsorted(edges, cur, side="left"), minlength=len(edges) + 1)
    p = np.maximum(ref_share / len(ref), floor)
    q = np.maximum(cur_share / len(cur), floor)
    return float(np.sum((q - p) * np.log(q / p)))


def categorical_psi(
    reference: Mapping[str, int], current: Mapping[str, int], floor: float = 1e-4
) -> float:
    """PSI between two category counts (a category missing from one side counts as the floor)."""
    keys = sorted(set(reference) | set(current))
    ref_total, cur_total = sum(reference.values()), sum(current.values())
    if ref_total == 0 or cur_total == 0:
        raise ValueError("both count tables need at least one observation")
    p = np.array([max(reference.get(k, 0) / ref_total, floor) for k in keys])
    q = np.array([max(current.get(k, 0) / cur_total, floor) for k in keys])
    return float(np.sum((q - p) * np.log(q / p)))


def ks_2samp(a: Sequence[float] | Array, b: Sequence[float] | Array) -> tuple[float, float]:
    """Two-sample Kolmogorov-Smirnov: (largest CDF gap, asymptotic p-value)."""
    x, y = np.sort(_clean(a)), np.sort(_clean(b))
    n, m = len(x), len(y)
    if n == 0 or m == 0:
        raise ValueError("both samples need at least one finite value")
    grid = np.concatenate([x, y])
    gap = np.abs(
        np.searchsorted(x, grid, side="right") / n - np.searchsorted(y, grid, side="right") / m
    )
    statistic = float(gap.max())
    effective = math.sqrt(n * m / (n + m))
    lam = (effective + 0.12 + 0.11 / effective) * statistic
    if lam < 1e-12:
        return statistic, 1.0
    total = 0.0
    for j in range(1, 101):
        term = (-1) ** (j - 1) * math.exp(-2 * j * j * lam * lam)
        total += term
        if abs(term) < 1e-12:
            break
    return statistic, float(min(1.0, max(0.0, 2 * total)))


def verdict(psi_value: float) -> str:
    if psi_value < PSI_STABLE:
        return "stable"
    return "moderate" if psi_value < PSI_MAJOR else "major"


@dataclass(frozen=True)
class FeatureDrift:
    name: str
    psi: float
    ks: float
    p_value: float
    verdict: str


def drift_table(
    features: Mapping[str, tuple[Sequence[float], Sequence[float]]],
) -> list[FeatureDrift]:
    """One row per feature, largest PSI first."""
    rows = []
    for name, (reference, current) in features.items():
        value = psi(reference, current)
        statistic, p_value = ks_2samp(reference, current)
        rows.append(FeatureDrift(name, value, statistic, p_value, verdict(value)))
    return sorted(rows, key=lambda r: r.psi, reverse=True)


@dataclass(frozen=True)
class EmbeddingDrift:
    centroid_cosine_distance: float  # 0 = the average meaning has not moved
    classifier_auc: (
        float  # 0.5 = reference and current cannot be told apart; 1.0 = trivially separable
    )
    n_reference: int
    n_current: int


def embedding_drift(
    reference: npt.ArrayLike, current: npt.ArrayLike, folds: int = 5, seed: int = 0
) -> EmbeddingDrift:
    """How far apart two sets of embedding vectors are, by centroid and by a classifier.

    The classifier is a logistic regression scored by cross-validated ROC AUC on a balanced draw,
    so a larger set does not look more different just because it is larger.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    ref = np.asarray(reference, dtype=np.float64)
    cur = np.asarray(current, dtype=np.float64)
    if ref.ndim != 2 or cur.ndim != 2 or ref.shape[1] != cur.shape[1]:
        raise ValueError("expected two 2-D arrays with the same number of columns")
    a, b = ref.mean(axis=0), cur.mean(axis=0)
    cosine = 1.0 - float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    rng = np.random.default_rng(seed)
    size = min(len(ref), len(cur))
    x = np.vstack([ref[rng.permutation(len(ref))[:size]], cur[rng.permutation(len(cur))[:size]]])
    y = np.array([0] * size + [1] * size)
    splits = max(2, min(folds, size))
    scores = cross_val_predict(
        LogisticRegression(max_iter=1000, C=0.1),
        x,
        y,
        cv=StratifiedKFold(splits, shuffle=True, random_state=seed),
        method="predict_proba",
    )[:, 1]
    return EmbeddingDrift(cosine, float(roc_auc_score(y, scores)), len(ref), len(cur))


@dataclass(frozen=True)
class Decay:
    baseline: float
    current: float
    drop: float
    flagged: bool


def quality_decay(baseline: float, current: float, tolerance: float) -> Decay:
    """Flag a drop of more than ``tolerance`` in a quality metric where higher is better.

    ``tolerance`` should come from how much the metric moves by chance (for a metric over n
    questions, one question moves it by 1/n), not from taste.
    """
    drop = baseline - current
    return Decay(baseline, current, drop, drop > tolerance)
