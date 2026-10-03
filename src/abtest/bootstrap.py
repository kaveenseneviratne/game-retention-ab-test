"""Bootstrap confidence intervals.

Used as an assumption-light cross-check on the parametric tests. If the two disagree,
that's worth investigating before anything goes in the memo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BootstrapResult:
    metric: str
    statistic: str
    point_estimate: float
    ci_low: float
    ci_high: float
    prob_below_zero: float
    n_resamples: int
    distribution: np.ndarray = field(repr=False, compare=False)


def bootstrap_proportion_diff(
    control: pd.Series,
    treatment: pd.Series,
    metric: str,
    n_resamples: int,
    alpha: float,
    rng: np.random.Generator,
) -> BootstrapResult:
    """Bootstrap the difference in conversion rates (treatment - control).

    Resampling n 0/1 values with replacement and taking the mean is the same as a single
    Binomial(n, p_hat) draw divided by n, so this is exact and runs in milliseconds
    instead of materialising millions of resampled rows.
    """
    c_n, t_n = len(control), len(treatment)
    c_rate, t_rate = float(control.mean()), float(treatment.mean())

    c_boot = rng.binomial(c_n, c_rate, size=n_resamples) / c_n
    t_boot = rng.binomial(t_n, t_rate, size=n_resamples) / t_n
    return _summarise(metric, "difference in proportions", t_rate - c_rate, t_boot - c_boot, alpha)


def bootstrap_median_diff(
    control: pd.Series,
    treatment: pd.Series,
    metric: str,
    n_resamples: int,
    alpha: float,
    rng: np.random.Generator,
    batch_size: int = 250,
) -> BootstrapResult:
    """Bootstrap the difference in medians (treatment - control).

    Resamples are drawn in batches so memory stays flat no matter how many we ask for.
    """
    c_values, t_values = control.to_numpy(), treatment.to_numpy()
    diffs = np.empty(n_resamples)

    for start in range(0, n_resamples, batch_size):
        size = min(batch_size, n_resamples - start)
        c_idx = rng.integers(0, len(c_values), size=(size, len(c_values)))
        t_idx = rng.integers(0, len(t_values), size=(size, len(t_values)))
        diffs[start : start + size] = np.median(t_values[t_idx], axis=1) - np.median(
            c_values[c_idx], axis=1
        )

    point = float(np.median(t_values) - np.median(c_values))
    return _summarise(metric, "difference in medians", point, diffs, alpha)


def _summarise(
    metric: str, statistic: str, point: float, diffs: np.ndarray, alpha: float
) -> BootstrapResult:
    low, high = np.quantile(diffs, [alpha / 2, 1 - alpha / 2])
    return BootstrapResult(
        metric=metric,
        statistic=statistic,
        point_estimate=point,
        ci_low=float(low),
        ci_high=float(high),
        prob_below_zero=float((diffs < 0).mean()),
        n_resamples=len(diffs),
        distribution=diffs,
    )
