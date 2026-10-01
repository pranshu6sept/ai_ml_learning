import pandas as pd
import pytest

from classical_ml.datasets import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET,
    make_credit_applicants,
)


def test_columns_and_size() -> None:
    df = make_credit_applicants(n_samples=500)
    assert len(df) == 500
    assert list(df.columns) == [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES, TARGET]


def test_same_seed_same_data() -> None:
    pd.testing.assert_frame_equal(
        make_credit_applicants(random_state=7), make_credit_applicants(random_state=7)
    )


def test_target_is_binary_and_imbalanced() -> None:
    df = make_credit_applicants()
    assert set(df[TARGET].unique()) == {0, 1}
    assert 0.05 < df[TARGET].mean() < 0.2


def test_has_some_missing_values() -> None:
    df = make_credit_applicants(missing_rate=0.05)
    assert df["annual_income"].isna().any()
    assert df["employment_type"].isna().any()
    assert not df[TARGET].isna().any()


def test_no_missing_values_when_rate_is_zero() -> None:
    assert not make_credit_applicants(missing_rate=0).isna().any().any()


def test_rejects_bad_missing_rate() -> None:
    with pytest.raises(ValueError):
        make_credit_applicants(missing_rate=1.0)
