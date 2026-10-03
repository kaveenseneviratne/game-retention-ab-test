"""Power and minimum detectable effect (MDE) for two-proportion tests.

Effect sizes are in Cohen's h, the scale statsmodels uses for proportions. The helpers
convert back to percentage points because that's what anyone reading the memo thinks in.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

_POWER = NormalIndPower()


def minimum_detectable_effect(
    baseline: float, n_per_group: int, alpha: float, power: float
) -> float:
    """Smallest absolute drop from `baseline` the test detects with the given power."""
    _check_rate(baseline)
    h = float(
        _POWER.solve_power(effect_size=None, nobs1=n_per_group, alpha=alpha, power=power, ratio=1.0)
    )
    # Invert Cohen's h: h = 2*asin(sqrt(p1)) - 2*asin(sqrt(p2)), solved for p2.
    phi = 2 * math.asin(math.sqrt(baseline))
    lower = math.sin(max(phi - h, 0.0) / 2) ** 2
    return baseline - lower


def required_sample_size(baseline: float, mde: float, alpha: float, power: float) -> int:
    """Users needed per group to detect an absolute drop of `mde` from `baseline`."""
    _check_rate(baseline)
    if not 0 < mde < baseline:
        raise ValueError("mde must be positive and smaller than the baseline rate.")
    h = abs(float(proportion_effectsize(baseline, baseline - mde)))
    n = _POWER.solve_power(effect_size=h, nobs1=None, alpha=alpha, power=power, ratio=1.0)
    return math.ceil(float(n))


def power_curve(
    baseline: float, n_per_group: int, alpha: float, effects: np.ndarray
) -> pd.DataFrame:
    """Achieved power across a range of absolute effect sizes."""
    _check_rate(baseline)
    rows = []
    for effect in effects:
        h = abs(float(proportion_effectsize(baseline, baseline - effect)))
        rows.append(
            {
                "effect": float(effect),
                "power": float(_POWER.power(effect_size=h, nobs1=n_per_group, alpha=alpha)),
            }
        )
    return pd.DataFrame(rows)


def _check_rate(rate: float) -> None:
    if not 0 < rate < 1:
        raise ValueError(f"Baseline rate must be strictly between 0 and 1, got {rate}.")
