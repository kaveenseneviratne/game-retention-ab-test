"""Beta-binomial comparison of two conversion rates.

Answers the question stakeholders actually ask ("how likely is B better than A, and
what do we lose if we're wrong?") instead of reporting a p-value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BayesianResult:
    metric: str
    prob_treatment_better: float
    expected_loss_treatment: float
    expected_loss_control: float
    credible_low: float
    credible_high: float
    n_samples: int


def beta_binomial_comparison(
    control: pd.Series,
    treatment: pd.Series,
    metric: str,
    rng: np.random.Generator,
    n_samples: int = 200_000,
    prior: tuple[float, float] = (1.0, 1.0),
    credible_mass: float = 0.95,
) -> BayesianResult:
    """Compare posteriors under a Beta prior (uniform by default).

    With ~45k users per group the prior barely moves the posterior, so a uniform prior is
    a defensible default rather than a modelling choice that needs justifying.
    """
    a0, b0 = prior
    c_success, c_n = int(control.sum()), len(control)
    t_success, t_n = int(treatment.sum()), len(treatment)

    c_post = rng.beta(a0 + c_success, b0 + c_n - c_success, size=n_samples)
    t_post = rng.beta(a0 + t_success, b0 + t_n - t_success, size=n_samples)
    diff = t_post - c_post

    tail = (1 - credible_mass) / 2
    low, high = np.quantile(diff, [tail, 1 - tail])
    return BayesianResult(
        metric=metric,
        prob_treatment_better=float((diff > 0).mean()),
        # Expected loss: how much rate we give up, on average, if we pick this arm and it's
        # actually the worse one.
        expected_loss_treatment=float(np.maximum(-diff, 0).mean()),
        expected_loss_control=float(np.maximum(diff, 0).mean()),
        credible_low=float(low),
        credible_high=float(high),
        n_samples=n_samples,
    )
