"""Preprocessing + model pipelines and cross-validation.

Everything that learns from data (imputer medians, scaler means, one-hot categories) lives inside
the ``Pipeline``, so cross-validation refits it on each training fold and never peeks at the
validation fold. That is the whole trick for avoiding preprocessing leakage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from classical_ml.datasets import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def debt_to_income(X: pd.DataFrame) -> npt.NDArray[np.float64]:
    """Loan amount / annual income as one column. NaN wherever income is missing."""
    ratio = X["loan_amount"] / X["annual_income"]
    return ratio.to_numpy(dtype=np.float64).reshape(-1, 1)


def _debt_to_income_names(
    transformer: FunctionTransformer, input_features: Sequence[str]
) -> npt.NDArray[np.object_]:
    return np.array(["debt_to_income"], dtype=object)


def build_preprocessor(
    numeric: Sequence[str] = NUMERIC_FEATURES,
    categorical: Sequence[str] = CATEGORICAL_FEATURES,
) -> ColumnTransformer:
    """Impute + scale numeric columns; impute + one-hot categorical columns.

    Also adds a ``debt_to_income`` feature computed from the raw loan and income columns.
    """
    numeric_steps = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical_steps = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    # The ratio is built from the raw columns (before imputing), so a missing income stays NaN
    # and is then imputed like any other numeric feature.
    ratio_steps = Pipeline(
        [
            ("ratio", FunctionTransformer(debt_to_income, feature_names_out=_debt_to_income_names)),
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        [
            ("num", numeric_steps, list(numeric)),
            ("cat", categorical_steps, list(categorical)),
            ("dti", ratio_steps, ["loan_amount", "annual_income"]),
        ]
    )


def build_pipeline(estimator: Any | None = None) -> Pipeline:
    """Preprocessor followed by ``estimator`` (default: logistic regression)."""
    if estimator is None:
        estimator = LogisticRegression(max_iter=1000)
    return Pipeline([("preprocess", build_preprocessor()), ("model", estimator)])


@dataclass(frozen=True)
class CVResult:
    scores: npt.NDArray[np.float64]

    @property
    def mean(self) -> float:
        return float(self.scores.mean())

    @property
    def std(self) -> float:
        return float(self.scores.std())

    def __str__(self) -> str:
        return f"{self.mean:.3f} ± {self.std:.3f} over {len(self.scores)} folds"


def cross_validate(
    pipeline: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 5,
    scoring: str = "roc_auc",
    random_state: int = 42,
) -> CVResult:
    """Stratified k-fold CV: every fold keeps the same class balance as ``y``."""
    folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    scores = cross_val_score(pipeline, X, y, cv=folds, scoring=scoring)
    return CVResult(scores=np.asarray(scores, dtype=np.float64))
