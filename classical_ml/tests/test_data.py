import pandas as pd
import pytest

from classical_ml.data import train_val_test_split


@pytest.fixture
def imbalanced_df() -> pd.DataFrame:
    n = 1000
    return pd.DataFrame({"x": range(n), "y": [1 if i % 20 == 0 else 0 for i in range(n)]})


def test_split_sizes_add_up(imbalanced_df: pd.DataFrame) -> None:
    train, val, test = train_val_test_split(imbalanced_df, target="y")
    assert len(train) + len(val) + len(test) == len(imbalanced_df)
    assert len(test) == pytest.approx(150, abs=2)


def test_split_is_stratified(imbalanced_df: pd.DataFrame) -> None:
    train, val, test = train_val_test_split(imbalanced_df, target="y")
    for part in (train, val, test):
        assert part["y"].mean() == pytest.approx(0.05, abs=0.01)


def test_splits_do_not_overlap(imbalanced_df: pd.DataFrame) -> None:
    train, val, test = train_val_test_split(imbalanced_df, target="y")
    assert set(train.index).isdisjoint(val.index)
    assert set(train.index).isdisjoint(test.index)
    assert set(val.index).isdisjoint(test.index)


def test_rejects_bad_sizes(imbalanced_df: pd.DataFrame) -> None:
    with pytest.raises(ValueError):
        train_val_test_split(imbalanced_df, target="y", val_size=0.6, test_size=0.5)
