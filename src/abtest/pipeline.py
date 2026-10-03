"""End-to-end analysis: load, check, test, decide, write outputs.

Kept separate from the CLI so the same run can be triggered from tests, a notebook or a
scheduler without going through argument parsing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from abtest import plots
from abtest.bayesian import BayesianResult, beta_binomial_comparison
from abtest.bootstrap import BootstrapResult, bootstrap_median_diff, bootstrap_proportion_diff
from abtest.config import Config
from abtest.data import CapSummary, cap_outliers, load_experiment_data, split_groups
from abtest.decision import Recommendation, recommend
from abtest.frequentist import (
    ProportionTestResult,
    RankTestResult,
    adjust_secondary,
    mann_whitney,
    two_proportion_test,
)
from abtest.power import minimum_detectable_effect, power_curve, required_sample_size
from abtest.quality import SRMResult, check_sample_ratio

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PowerSummary:
    baseline: float
    n_per_group: int
    mde: float
    n_needed_for_observed: int | None


@dataclass(frozen=True)
class AnalysisResults:
    config: Config
    n_users: int
    srm: SRMResult
    cap: CapSummary
    power: PowerSummary
    primary: ProportionTestResult
    secondary: list[ProportionTestResult]
    guardrail: RankTestResult
    bootstrap_primary: BootstrapResult
    bootstrap_guardrail: BootstrapResult
    bayesian: BayesianResult
    recommendation: Recommendation
    figures: dict[str, Path]


def run_analysis(config: Config) -> AnalysisResults:
    exp, metrics, an = config.experiment, config.metrics, config.analysis
    rng = np.random.default_rng(an.random_seed)

    df = load_experiment_data(config)

    srm = check_sample_ratio(df[exp.group_column], [exp.control, exp.treatment], an.srm_alpha)
    if srm.passed:
        logger.info("SRM check passed (p = %.3f)", srm.p_value)
    else:
        # Keep going so the report shows everything, but the decision step will refuse
        # to recommend anything while this is unresolved.
        logger.warning("SRM check FAILED (p = %.2g): %s", srm.p_value, srm.observed)

    capped_col = f"{metrics.guardrail}_capped"
    df[capped_col], cap = cap_outliers(df[metrics.guardrail], an.guardrail_cap_quantile)

    primary = two_proportion_test(
        *split_groups(df, config, metrics.primary), metric=metrics.primary, alpha=an.alpha
    )
    secondary = adjust_secondary(
        [
            two_proportion_test(*split_groups(df, config, m), metric=m, alpha=an.alpha)
            for m in metrics.secondary
        ]
    )

    g_control, g_treatment = split_groups(df, config, capped_col)
    g_control, g_treatment = (
        g_control.rename(metrics.guardrail),
        g_treatment.rename(metrics.guardrail),
    )
    guardrail = mann_whitney(g_control, g_treatment, metric=metrics.guardrail, alpha=an.alpha)

    n_per_group = min(primary.control_n, primary.treatment_n)
    mde = minimum_detectable_effect(primary.control_rate, n_per_group, an.alpha, an.power)
    observed = abs(primary.abs_diff)
    power = PowerSummary(
        baseline=primary.control_rate,
        n_per_group=n_per_group,
        mde=mde,
        n_needed_for_observed=(
            required_sample_size(primary.control_rate, observed, an.alpha, an.power)
            if 0 < observed < primary.control_rate
            else None
        ),
    )
    logger.info("MDE at %.0f%% power: %.2f pp", an.power * 100, mde * 100)

    p_control, p_treatment = split_groups(df, config, metrics.primary)
    boot_primary = bootstrap_proportion_diff(
        p_control, p_treatment, metrics.primary, an.bootstrap_resamples, an.alpha, rng
    )
    logger.info("Bootstrapping the guardrail median (%d resamples)...", an.bootstrap_resamples)
    boot_guardrail = bootstrap_median_diff(
        g_control, g_treatment, metrics.guardrail, an.bootstrap_resamples, an.alpha, rng
    )
    bayes = beta_binomial_comparison(p_control, p_treatment, metrics.primary, rng)

    rec = recommend(srm, primary, guardrail, mde)
    logger.info("Recommendation: %s", rec.decision.value.upper())

    figures = _make_figures(config, primary, secondary, boot_primary, g_control, g_treatment, power)

    return AnalysisResults(
        config=config,
        n_users=len(df),
        srm=srm,
        cap=cap,
        power=power,
        primary=primary,
        secondary=secondary,
        guardrail=guardrail,
        bootstrap_primary=boot_primary,
        bootstrap_guardrail=boot_guardrail,
        bayesian=bayes,
        recommendation=rec,
        figures=figures,
    )


def _make_figures(
    config: Config,
    primary: ProportionTestResult,
    secondary: list[ProportionTestResult],
    boot_primary: BootstrapResult,
    g_control: pd.Series,
    g_treatment: pd.Series,
    power: PowerSummary,
) -> dict[str, Path]:
    exp, an = config.experiment, config.analysis
    fig_dir = config.output_dir / "figures"
    labels = (exp.control, exp.treatment)
    effects = np.linspace(0.0005, max(3 * power.mde, 0.01), 60)

    return {
        "retention": plots.plot_retention(
            [primary, *secondary], labels, fig_dir / "retention_by_group.png"
        ),
        "bootstrap": plots.plot_bootstrap(boot_primary, fig_dir / "bootstrap_primary.png"),
        "power": plots.plot_power_curve(
            power_curve(power.baseline, power.n_per_group, an.alpha, effects),
            primary.abs_diff,
            an.power,
            fig_dir / "power_curve.png",
        ),
        "guardrail": plots.plot_guardrail(
            g_control, g_treatment, labels, fig_dir / "guardrail_distribution.png"
        ),
    }
