import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from classical_ml.datasets import TARGET, make_credit_applicants
from classical_ml.pipeline import build_pipeline, build_preprocessor, cross_validate


@pytest.fixture(scope="module")
def data() -> tuple[pd.DataFrame, pd.Series]:
    df = make_credit_applicants(n_samples=2000)
    return df.drop(columns=TARGET), df[TARGET]


def test_preprocessor_removes_missing_values(data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, _ = data
    out = build_preprocessor().fit_transform(X)
    assert not np.isnan(out).any()


def test_preprocessor_one_hot_encodes_categories(data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, _ = data
    out = build_preprocessor().fit_transform(X)
    # 5 numeric + 4 employment types + 4 regions + 2 owns_home values + debt_to_income
    assert out.shape == (len(X), 5 + 4 + 4 + 2 + 1)


def test_preprocessor_tolerates_unseen_category(data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, _ = data
    pre = build_preprocessor().fit(X)
    new_row = X.iloc[[0]].assign(region="mars")
    assert pre.transform(new_row).shape == (1, 16)


def test_pipeline_beats_chance(data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, y = data
    result = cross_validate(build_pipeline(), X, y, n_splits=5)
    assert len(result.scores) == 5
    assert result.mean > 0.7


def test_logistic_regression_coefficients_match_generator_signs(
    data: tuple[pd.DataFrame, pd.Series],
) -> None:
    X, y = data
    fitted = build_pipeline().fit(X, y)
    coefs = dict(
        zip(
            fitted.named_steps["preprocess"].get_feature_names_out(),
            fitted.named_steps["model"].coef_[0],
            strict=False,
        )
    )

    assert coefs["dti__debt_to_income"] > 0
    assert coefs["num__num_late_payments"] > 0
    assert coefs["num__credit_history_months"] < 0
    assert coefs["cat__employment_type_unemployed"] > 0
    assert coefs["cat__owns_home_yes"] < 0


def test_dummy_model_is_at_chance(data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, y = data
    result = cross_validate(build_pipeline(DummyClassifier()), X, y, n_splits=3)
    assert result.mean == pytest.approx(0.5)
