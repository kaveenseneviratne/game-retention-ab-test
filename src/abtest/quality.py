"""Experiment health checks that run before any outcome is looked at."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd
from scipy.stats import chisquare


@dataclass(frozen=True)
class SRMResult:
    observed: dict[str, int]
    expected_shares: dict[str, float]
    chi2: float
    p_value: float
    alpha: float

    @property
    def passed(self) -> bool:
        return self.p_value >= self.alpha


def check_sample_ratio(
    groups: pd.Series,
    group_names: Sequence[str],
    alpha: float,
    expected_shares: Sequence[float] | None = None,
) -> SRMResult:
    """Chi-square test for sample ratio mismatch (SRM).

    If the split we got is far from the split we designed, randomisation or logging is
    broken somewhere and the effect estimates can't be trusted, however good they look.
    """
    if expected_shares is None:
        expected_shares = [1 / len(group_names)] * len(group_names)
    if abs(sum(expected_shares) - 1) > 1e-9:
        raise ValueError("expected_shares must sum to 1.")

    counts = groups.value_counts()
    observed = [int(counts.get(name, 0)) for name in group_names]
    total = sum(observed)
    expected = [share * total for share in expected_shares]

    stat, p_value = chisquare(observed, expected)
    return SRMResult(
        observed=dict(zip(group_names, observed, strict=True)),
        expected_shares=dict(zip(group_names, expected_shares, strict=True)),
        chi2=float(stat),
        p_value=float(p_value),
        alpha=alpha,
    )
