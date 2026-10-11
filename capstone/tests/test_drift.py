"""Drift statistics: checked by hand, against SciPy, and on data with a known shift."""

from __future__ import annotations

import math

import numpy as np
import pytest

from payments_rag.drift import (
    categorical_psi,
    drift_table,
    embedding_drift,
    ks_2samp,
    psi,
    quality_decay,
    verdict,
)

RNG = np.random.default_rng(0)


# ---- PSI ----


def test_identical_samples_have_zero_psi() -> None:
    sample = RNG.normal(size=500)

    assert psi(sample, sample) == pytest.approx(0.0, abs=1e-12)


def test_psi_matches_a_value_worked_by_hand() -> None:
    reference = np.arange(100, dtype=float)  # ten equal bins of ten values each
    current = np.full(50, 99.0)  # everything in the last bin

    # nine bins: p = 0.1, q = floor 1e-4;  last bin: p = 0.1, q = 1.0
    floor = 1e-4
    expected = 9 * (floor - 0.1) * math.log(floor / 0.1) + (1.0 - 0.1) * math.log(1.0 / 0.1)

    assert psi(reference, current) == pytest.approx(expected, rel=1e-9)


def test_a_shifted_distribution_has_a_large_psi_and_a_same_distribution_a_small_one() -> None:
    reference = RNG.normal(0, 1, 5000)

    same = psi(reference, RNG.normal(0, 1, 5000))
    shifted = psi(reference, RNG.normal(1.0, 1, 5000))
    wider = psi(reference, RNG.normal(0, 2.0, 5000))

    assert same < 0.02
    assert shifted > 0.25 and wider > 0.25


def test_values_outside_the_reference_range_still_count() -> None:
    reference = np.linspace(0, 1, 200)

    assert psi(reference, np.full(100, 50.0)) > 1.0


def test_non_finite_values_are_ignored_and_empty_samples_are_an_error() -> None:
    assert psi([1, 2, 3, 4, 5, np.nan], [1, 2, 3, 4, 5, np.inf]) == pytest.approx(0.0, abs=1e-12)
    with pytest.raises(ValueError):
        psi([], [1.0])


def test_a_constant_feature_does_not_crash() -> None:
    assert psi(np.ones(100), np.ones(100)) == pytest.approx(0.0, abs=1e-12)
    assert psi(np.ones(100), np.full(100, 2.0)) > 1.0


def test_categorical_psi_and_the_verdict_cut_offs() -> None:
    assert categorical_psi({"a": 50, "b": 50}, {"a": 50, "b": 50}) == pytest.approx(0.0, abs=1e-12)
    assert categorical_psi({"a": 90, "b": 10}, {"a": 10, "b": 90}) > 1.0
    assert categorical_psi({"a": 10}, {"b": 10}) > 1.0  # a brand-new category
    assert [verdict(0.05), verdict(0.15), verdict(0.40)] == ["stable", "moderate", "major"]


# ---- KS ----


def test_ks_equals_scipys_statistic_and_is_close_on_the_p_value() -> None:
    scipy_stats = pytest.importorskip("scipy.stats")
    a, b = RNG.normal(0, 1, 400), RNG.normal(0.3, 1, 350)

    mine = ks_2samp(a, b)
    theirs = scipy_stats.ks_2samp(a, b, method="asymp")

    assert mine[0] == pytest.approx(theirs.statistic, abs=1e-12)
    assert mine[1] == pytest.approx(theirs.pvalue, abs=0.02)


def test_ks_extremes() -> None:
    same = RNG.normal(size=200)
    assert ks_2samp(same, same) == (0.0, 1.0)

    statistic, p_value = ks_2samp(np.zeros(300), np.ones(300))
    assert statistic == 1.0 and p_value < 1e-10

    with pytest.raises(ValueError):
        ks_2samp([], [1.0])


def test_the_ks_gap_is_the_size_of_the_difference_not_just_whether_there_is_one() -> None:
    a = RNG.normal(0, 1, 20000)

    small, _ = ks_2samp(a, RNG.normal(0.02, 1, 20000))
    large, _ = ks_2samp(a, RNG.normal(1.0, 1, 20000))

    assert small < 0.05 < 0.3 < large


# ---- the table ----


def test_the_table_lists_the_most_drifted_feature_first() -> None:
    base = RNG.normal(size=2000)
    table = drift_table(
        {"stable": (base, RNG.normal(size=2000)), "moved": (base, RNG.normal(2.0, 1, 2000))}
    )

    assert [row.name for row in table] == ["moved", "stable"]
    assert table[0].verdict == "major" and table[1].verdict == "stable"


# ---- embeddings ----


def clouds(shift: float, n: int = 200, dims: int = 32) -> tuple[np.ndarray, np.ndarray]:
    ref = RNG.normal(0, 1, (n, dims)) + 3.0  # a common direction so cosine distances are meaningful
    cur = RNG.normal(0, 1, (n, dims)) + 3.0
    cur[:, :4] += shift
    return ref, cur


def test_embeddings_from_the_same_distribution_cannot_be_told_apart() -> None:
    ref, cur = clouds(0.0)

    result = embedding_drift(ref, cur)

    assert result.classifier_auc < 0.65 and result.centroid_cosine_distance < 0.01


def test_embeddings_that_moved_are_easy_to_separate() -> None:
    ref, cur = clouds(2.5)

    result = embedding_drift(ref, cur)

    assert result.classifier_auc > 0.95
    assert result.centroid_cosine_distance > embedding_drift(*clouds(0.0)).centroid_cosine_distance


def test_the_classifier_is_not_fooled_by_unequal_sizes() -> None:
    ref, cur = clouds(0.0, n=400)

    result = embedding_drift(ref, cur[:60])

    assert result.classifier_auc < 0.75 and (result.n_reference, result.n_current) == (400, 60)


def test_embedding_inputs_must_match() -> None:
    with pytest.raises(ValueError):
        embedding_drift(np.zeros((5, 3)), np.zeros((5, 4)))


# ---- quality decay ----


def test_a_quality_drop_beyond_the_tolerance_is_flagged() -> None:
    assert quality_decay(0.72, 0.60, tolerance=0.05).flagged is True
    assert quality_decay(0.72, 0.70, tolerance=0.05).flagged is False
    assert quality_decay(0.72, 0.80, tolerance=0.05).flagged is False  # an improvement is not decay
    assert quality_decay(0.72, 0.60, tolerance=0.05).drop == pytest.approx(0.12)
