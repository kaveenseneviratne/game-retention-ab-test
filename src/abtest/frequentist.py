"""Classical hypothesis tests for binary and skewed count metrics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

import pandas as pd
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest


@dataclass(frozen=True)
class ProportionTestResult:
    metric: str
    control_n: int
    treatment_n: int
    control_rate: float
    treatment_rate: float
    abs_diff: float
    rel_diff: float
    ci_low: float
    ci_high: float
    z_stat: float
    p_value: float
    alpha: float
    p_value_adjusted: float | None = None

    @property
    def significant(self) -> bool:
        p = self.p_value if self.p_value_adjusted is None else self.p_value_adjusted
        return p < self.alpha


@dataclass(frozen=True)
class RankTestResult:
    metric: str
    control_median: float
    treatment_median: float
    control_mean: float
    treatment_mean: float
    u_stat: float
    p_value: float
    rank_biserial: float
    alpha: float

    @property
    def significant(self) -> bool:
        return self.p_value < self.alpha


def two_proportion_test(
    control: pd.Series, treatment: pd.Series, metric: str, alpha: float
) -> ProportionTestResult:
    """Two-sided z-test plus a Wald CI for (treatment - control)."""
    c_n, t_n = len(control), len(treatment)
    if c_n == 0 or t_n == 0:
        raise ValueError("Both groups need at least one observation.")
    c_success, t_success = int(control.sum()), int(treatment.sum())

    z_stat, p_value = proportions_ztest([t_success, c_success], [t_n, c_n])
    ci_low, ci_high = confint_proportions_2indep(
        t_success, t_n, c_success, c_n, method="wald", compare="diff", alpha=alpha
    )

    c_rate, t_rate = c_success / c_n, t_success / t_n
    return ProportionTestResult(
        metric=metric,
        control_n=c_n,
        treatment_n=t_n,
        control_rate=c_rate,
        treatment_rate=t_rate,
        abs_diff=t_rate - c_rate,
        rel_diff=(t_rate - c_rate) / c_rate if c_rate else float("nan"),
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        z_stat=float(z_stat),
        p_value=float(p_value),
        alpha=alpha,
    )


def adjust_secondary(
    results: Sequence[ProportionTestResult], method: str = "holm"
) -> list[ProportionTestResult]:
    """Correct p-values across secondary metrics.

    The primary metric was named in advance, so it keeps its raw p-value. Secondary
    metrics are where the multiple-comparisons risk sits.
    """
    if not results:
        return []
    _, adjusted, _, _ = multipletests([r.p_value for r in results], method=method)
    return [replace(r, p_value_adjusted=float(p)) for r, p in zip(results, adjusted, strict=True)]


def mann_whitney(
    control: pd.Series, treatment: pd.Series, metric: str, alpha: float
) -> RankTestResult:
    """Rank-based test for heavily skewed metrics like rounds played.

    Rank-biserial correlation is the effect size: 0 means no shift, positive means
    treatment users tend to have higher values.
    """
    res = mannwhitneyu(treatment, control, alternative="two-sided")
    n_pairs = len(treatment) * len(control)
    return RankTestResult(
        metric=metric,
        control_median=float(control.median()),
        treatment_median=float(treatment.median()),
        control_mean=float(control.mean()),
        treatment_mean=float(treatment.mean()),
        u_stat=float(res.statistic),
        p_value=float(res.pvalue),
        rank_biserial=float(2 * res.statistic / n_pairs - 1),
        alpha=alpha,
    )
