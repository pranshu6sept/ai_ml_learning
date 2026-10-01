"""A synthetic loan-applicant dataset, so Week 1 works offline and looks like the real thing.

The target ``defaulted`` is generated from a known logistic formula, which means you can check
whether a model recovers sensible relationships (more late payments -> more defaults, etc.).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TARGET = "defaulted"
NUMERIC_FEATURES = [
    "age",
    "annual_income",
    "loan_amount",
    "credit_history_months",
    "num_late_payments",
]
CATEGORICAL_FEATURES = ["employment_type", "region", "owns_home"]

_EMPLOYMENT_TYPES = ["salaried", "self_employed", "contract", "unemployed"]
_EMPLOYMENT_RISK = {"salaried": 0.0, "self_employed": 0.4, "contract": 0.6, "unemployed": 1.5}
_REGIONS = ["north", "south", "east", "west"]


def make_credit_applicants(
    n_samples: int = 5000,
    missing_rate: float = 0.05,
    random_state: int = 0,
) -> pd.DataFrame:
    """Return one row per loan applicant with mixed numeric/categorical features and some NaNs.

    About 10% of applicants default. ``region`` has no effect on the target on purpose: a good
    model should learn to (mostly) ignore it.
    """
    if not 0 <= missing_rate < 1:
        raise ValueError("missing_rate must be in [0, 1)")

    rng = np.random.default_rng(random_state)

    age = rng.integers(21, 71, size=n_samples)
    annual_income = np.round(rng.lognormal(mean=11.0, sigma=0.5, size=n_samples), -2)
    loan_amount = np.round(annual_income * rng.uniform(0.1, 1.2, size=n_samples), -2)
    history_share = rng.uniform(0.2, 1.0, size=n_samples)
    credit_history_months = np.clip((age - 18) * 12 * history_share, 0, None)
    num_late_payments = rng.poisson(lam=0.8, size=n_samples)
    employment_type = rng.choice(_EMPLOYMENT_TYPES, size=n_samples, p=[0.6, 0.2, 0.15, 0.05])
    region = rng.choice(_REGIONS, size=n_samples)
    owns_home = rng.choice(["yes", "no"], size=n_samples, p=[0.45, 0.55])

    # Ground-truth risk score. Vectorised NumPy: one expression for all rows, no Python loop.
    debt_to_income = loan_amount / annual_income
    logit = (
        -3.6
        + 2.2 * debt_to_income
        + 0.55 * num_late_payments
        - 0.004 * credit_history_months
        + np.vectorize(_EMPLOYMENT_RISK.__getitem__)(employment_type)
        - 0.3 * (owns_home == "yes")
    )
    p_default = 1 / (1 + np.exp(-logit))
    defaulted = (rng.uniform(size=n_samples) < p_default).astype(int)

    df = pd.DataFrame(
        {
            "age": age,
            "annual_income": annual_income,
            "loan_amount": loan_amount,
            "credit_history_months": np.round(credit_history_months),
            "num_late_payments": num_late_payments,
            "employment_type": employment_type,
            "region": region,
            "owns_home": owns_home,
            TARGET: defaulted,
        }
    )

    # Real data has gaps. Blank out a few cells in columns where that is realistic.
    for col in ("annual_income", "credit_history_months", "employment_type"):
        mask = rng.uniform(size=n_samples) < missing_rate
        df.loc[mask, col] = np.nan

    return df
