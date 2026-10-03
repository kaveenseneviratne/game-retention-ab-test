"""Tests for the statistical building blocks, checked against known synthetic truths."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from abtest.bayesian import beta_binomial_comparison
from abtest.bootstrap import bootstrap_median_diff, bootstrap_proportion_diff
from abtest.frequentist import adjust_secondary, mann_whitney, two_proportion_test
from abtest.power import minimum_detectable_effect, power_curve, required_sample_size
from abtest.quality import check_sample_ratio

from .conftest import make_experiment_frame


def _arms(df: pd.DataFrame, column: str) -> tuple[pd.Series, pd.Series]:
    return (
        df.loc[df["version"] == "gate_30", column],
        df.loc[df["version"] == "gate_40", column],
    )


# --- sample ratio mismatch -------------------------------------------------------------


def test_srm_passes_on_balanced_split() -> None:
    groups = pd.Series(["a"] * 50_000 + ["b"] * 50_050)
    assert check_sample_ratio(groups, ["a", "b"], alpha=0.001).passed


def test_srm_fails_on_skewed_split() -> None:
    groups = pd.Series(["a"] * 50_000 + ["b"] * 48_000)
    result = check_sample_ratio(groups, ["a", "b"], alpha=0.001)
    assert not result.passed
    assert result.observed == {"a": 50_000, "b": 48_000}


def test_srm_rejects_bad_shares() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        check_sample_ratio(pd.Series(["a", "b"]), ["a", "b"], 0.001, [0.5, 0.6])


# --- frequentist -----------------------------------------------------------------------


def test_proportion_test_matches_hand_calculation() -> None:
    control = pd.Series([True] * 200 + [False] * 800)
    treatment = pd.Series([True] * 150 + [False] * 850)
    r = two_proportion_test(control, treatment, "m", alpha=0.05)

    assert r.abs_diff == pytest.approx(-0.05)
    assert r.rel_diff == pytest.approx(-0.25)
    # pooled z for this table, worked out by hand
    pooled = 350 / 2000
    se = np.sqrt(pooled * (1 - pooled) * (2 / 1000))
    assert r.z_stat == pytest.approx(-0.05 / se, rel=1e-6)
    assert r.ci_low < r.abs_diff < r.ci_high
    assert r.significant


def test_identical_groups_are_not_significant() -> None:
    s = pd.Series([True, False] * 5_000)
    r = two_proportion_test(s, s, "m", alpha=0.05)
    assert r.p_value == pytest.approx(1.0)
    assert not r.significant


def test_empty_group_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        two_proportion_test(pd.Series([], dtype=bool), pd.Series([True]), "m", 0.05)


def test_detects_planted_effect(experiment_df: pd.DataFrame) -> None:
    r = two_proportion_test(*_arms(experiment_df, "retention_7"), "retention_7", alpha=0.05)
    assert r.ci_low < -0.01 + 0.01 and r.ci_high > -0.01 - 0.01  # CI near the true -1 pp
    assert r.abs_diff < 0


def test_holm_adjustment_never_lowers_p_values(experiment_df: pd.DataFrame) -> None:
    raw = [
        two_proportion_test(*_arms(experiment_df, m), m, alpha=0.05)
        for m in ("retention_1", "retention_7")
    ]
    adjusted = adjust_secondary(raw)
    for before, after in zip(raw, adjusted, strict=True):
        assert after.p_value_adjusted is not None
        assert after.p_value_adjusted >= before.p_value
    assert adjust_secondary([]) == []


def test_mann_whitney_effect_direction() -> None:
    rng = np.random.default_rng(3)
    control = pd.Series(rng.poisson(20, 5_000))
    treatment = pd.Series(rng.poisson(25, 5_000))
    r = mann_whitney(control, treatment, "rounds", alpha=0.05)
    assert r.significant
    assert r.rank_biserial > 0
    assert r.treatment_median > r.control_median


# --- power -----------------------------------------------------------------------------


def test_mde_and_sample_size_are_inverse() -> None:
    mde = minimum_detectable_effect(0.19, n_per_group=45_000, alpha=0.05, power=0.8)
    n = required_sample_size(0.19, mde, alpha=0.05, power=0.8)
    assert n == pytest.approx(45_000, rel=0.01)


def test_mde_shrinks_with_more_users() -> None:
    small = minimum_detectable_effect(0.19, 10_000, 0.05, 0.8)
    large = minimum_detectable_effect(0.19, 100_000, 0.05, 0.8)
    assert large < small


def test_power_curve_is_increasing() -> None:
    curve = power_curve(0.19, 45_000, 0.05, np.linspace(0.001, 0.02, 20))
    assert curve["power"].is_monotonic_increasing
    assert curve["power"].iloc[-1] > 0.99


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1])
def test_power_rejects_invalid_baseline(bad: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        minimum_detectable_effect(bad, 1_000, 0.05, 0.8)


# --- bootstrap -------------------------------------------------------------------------


def test_bootstrap_proportion_agrees_with_z_test(experiment_df: pd.DataFrame) -> None:
    control, treatment = _arms(experiment_df, "retention_7")
    z = two_proportion_test(control, treatment, "retention_7", alpha=0.05)
    boot = bootstrap_proportion_diff(
        control, treatment, "retention_7", 5_000, 0.05, np.random.default_rng(0)
    )
    assert boot.point_estimate == pytest.approx(z.abs_diff)
    assert boot.ci_low == pytest.approx(z.ci_low, abs=0.002)
    assert boot.ci_high == pytest.approx(z.ci_high, abs=0.002)


def test_bootstrap_is_reproducible(experiment_df: pd.DataFrame) -> None:
    control, treatment = _arms(experiment_df, "retention_7")
    a = bootstrap_proportion_diff(control, treatment, "m", 500, 0.05, np.random.default_rng(7))
    b = bootstrap_proportion_diff(control, treatment, "m", 500, 0.05, np.random.default_rng(7))
    np.testing.assert_array_equal(a.distribution, b.distribution)


def test_bootstrap_median_handles_uneven_batches() -> None:
    rng = np.random.default_rng(0)
    control, treatment = pd.Series(rng.poisson(10, 800)), pd.Series(rng.poisson(10, 800))
    r = bootstrap_median_diff(control, treatment, "m", 333, 0.05, rng, batch_size=100)
    assert r.n_resamples == 333
    assert r.ci_low <= r.point_estimate <= r.ci_high


# --- bayesian --------------------------------------------------------------------------


def test_bayesian_is_a_coin_flip_for_identical_arms() -> None:
    s = pd.Series([True, False] * 10_000)
    r = beta_binomial_comparison(s, s, "m", np.random.default_rng(0))
    assert r.prob_treatment_better == pytest.approx(0.5, abs=0.01)


def test_bayesian_is_confident_on_large_effect() -> None:
    df = make_experiment_frame(rates=(0.20, 0.15))
    r = beta_binomial_comparison(*_arms(df, "retention_7"), "m", np.random.default_rng(0))
    assert r.prob_treatment_better < 0.001
    assert r.expected_loss_treatment > r.expected_loss_control
    assert r.credible_high < 0
