"""Data loading and splitting helpers."""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split


def train_val_test_split(
    df: pd.DataFrame,
    target: str,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split into train/val/test, stratified on ``target`` so rare classes appear in every split."""
    if not 0 < val_size + test_size < 1:
        raise ValueError("val_size + test_size must be between 0 and 1")

    train, holdout = train_test_split(
        df,
        test_size=val_size + test_size,
        stratify=df[target],
        random_state=random_state,
    )
    val, test = train_test_split(
        holdout,
        test_size=test_size / (val_size + test_size),
        stratify=holdout[target],
        random_state=random_state,
    )
    return train, val, test
