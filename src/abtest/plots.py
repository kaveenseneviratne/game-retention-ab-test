"""Figures for the README and the decision memo.

Every function takes results objects and an output path, and returns the path it wrote.
Nothing here computes statistics; that keeps the charts consistent with the report.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed in CI or on a server

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter
from statsmodels.stats.proportion import proportion_confint

from abtest.bootstrap import BootstrapResult
from abtest.frequentist import ProportionTestResult

CONTROL_COLOR = "#8C8C8C"
TREATMENT_COLOR = "#2A6FDB"
ACCENT_COLOR = "#D1495B"


def _style(ax: Axes, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", pad=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)


def _save(fig: Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_retention(
    results: Sequence[ProportionTestResult], labels: tuple[str, str], path: Path
) -> Path:
    """Grouped bars of each binary metric with 95% Wilson intervals per arm."""
    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = np.arange(len(results))
    width = 0.36

    for offset, arm, color, label in (
        (-width / 2, "control", CONTROL_COLOR, labels[0]),
        (width / 2, "treatment", TREATMENT_COLOR, labels[1]),
    ):
        rates, errors = [], []
        for r in results:
            n = r.control_n if arm == "control" else r.treatment_n
            rate = r.control_rate if arm == "control" else r.treatment_rate
            low, high = proportion_confint(round(rate * n), n, method="wilson")
            rates.append(rate)
            errors.append([rate - low, high - rate])
        ax.bar(x + offset, rates, width, color=color, label=label)
        ax.errorbar(
            x + offset,
            rates,
            yerr=np.array(errors).T,
            fmt="none",
            ecolor="black",
            capsize=4,
            linewidth=1,
        )
        for xi, rate in zip(x + offset, rates, strict=True):
            ax.text(xi, rate + 0.012, f"{rate:.1%}", ha="center", fontsize=9)

    ax.set_xticks(x, [r.metric.replace("_", " ").title() for r in results])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_ylim(0, max(max(r.control_rate, r.treatment_rate) for r in results) * 1.25)
    ax.legend(frameon=False)
    _style(ax, "Retention by group (95% CI)")
    return _save(fig, path)


def plot_bootstrap(result: BootstrapResult, path: Path) -> Path:
    """Histogram of bootstrapped differences with the CI and zero marked."""
    fig, ax = plt.subplots(figsize=(7, 4))
    scale = 100 if "proportion" in result.statistic else 1
    ax.hist(result.distribution * scale, bins=60, color=TREATMENT_COLOR, alpha=0.8)
    ax.axvline(0, color="black", linewidth=1)
    for bound in (result.ci_low, result.ci_high):
        ax.axvline(bound * scale, color=ACCENT_COLOR, linestyle="--", linewidth=1)

    unit = "percentage points" if scale == 100 else "units"
    ax.set_xlabel(f"Treatment minus control ({unit})")
    ax.set_ylabel("Bootstrap resamples")
    _style(ax, f"Bootstrap distribution: {result.metric}")
    return _save(fig, path)


def plot_power_curve(
    curve: pd.DataFrame, observed_effect: float, target_power: float, path: Path
) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(curve["effect"] * 100, curve["power"], color=TREATMENT_COLOR, linewidth=2)
    ax.axhline(
        target_power,
        color=CONTROL_COLOR,
        linestyle="--",
        linewidth=1,
        label=f"{target_power:.0%} power",
    )
    ax.axvline(
        abs(observed_effect) * 100,
        color=ACCENT_COLOR,
        linestyle=":",
        linewidth=1.5,
        label="Observed effect",
    )
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_xlabel("True effect size (absolute, percentage points)")
    ax.set_ylabel("Probability of detecting it")
    ax.legend(frameon=False, loc="lower right")
    _style(ax, "What this test could detect")
    return _save(fig, path)


def plot_guardrail(
    control: pd.Series, treatment: pd.Series, labels: tuple[str, str], path: Path
) -> Path:
    """Overlaid distributions on a log x-axis; rounds played spans several orders of magnitude."""
    fig, ax = plt.subplots(figsize=(7, 4))
    upper = max(control.max(), treatment.max())
    bins = np.logspace(0, np.log10(upper + 1), 50).tolist()

    # +1 so users with zero rounds still show up on a log scale
    ax.hist(control + 1, bins=bins, alpha=0.6, color=CONTROL_COLOR, label=labels[0])
    ax.hist(treatment + 1, bins=bins, alpha=0.6, color=TREATMENT_COLOR, label=labels[1])
    ax.set_xscale("log")
    ax.set_xlabel(f"{control.name} + 1 (log scale)")
    ax.set_ylabel("Users")
    ax.legend(frameon=False)
    _style(ax, "Guardrail: game rounds played")
    return _save(fig, path)
