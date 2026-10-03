"""Loading, validating and preparing the raw experiment export.

Validation fails loudly. An analysis that runs on a silently broken file is worse
than one that doesn't run at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from abtest.config import Config

logger = logging.getLogger(__name__)


class DataValidationError(ValueError):
    """Raised when the raw data doesn't match what the experiment config expects."""


@dataclass(frozen=True)
class CapSummary:
    column: str
    quantile: float
    threshold: float
    n_capped: int
    raw_max: float


def load_experiment_data(config: Config) -> pd.DataFrame:
    path = config.data_path
    if not path.is_file():
        raise FileNotFoundError(
            f"Data file not found at {path}. Download the Cookie Cats CSV from Kaggle "
            "and place it there (see README)."
        )
    df = pd.read_csv(path)
    logger.info("Loaded %s rows from %s", f"{len(df):,}", path)
    return validate(df, config)


def validate(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Check the schema and return a cleaned copy with binary metrics as bools."""
    exp, metrics = config.experiment, config.metrics
    required = [exp.unit_column, exp.group_column, *metrics.binary, metrics.guardrail]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")

    out = df[required].copy()

    null_counts = out.isna().sum()
    if null_counts.any():
        raise DataValidationError(f"Null values found: {null_counts[null_counts > 0].to_dict()}")

    n_dupes = int(out[exp.unit_column].duplicated().sum())
    if n_dupes:
        raise DataValidationError(
            f"{n_dupes} duplicated {exp.unit_column} values. Each user must appear once, "
            "otherwise observations aren't independent."
        )

    groups = set(out[exp.group_column].unique())
    expected = {exp.control, exp.treatment}
    if groups != expected:
        raise DataValidationError(f"Expected groups {sorted(expected)}, found {sorted(groups)}")

    for col in metrics.binary:
        out[col] = _to_bool(out[col], col)

    if not pd.api.types.is_numeric_dtype(out[metrics.guardrail]):
        raise DataValidationError(f"Guardrail column {metrics.guardrail!r} must be numeric.")
    if (out[metrics.guardrail] < 0).any():
        raise DataValidationError(f"Guardrail column {metrics.guardrail!r} has negative values.")

    return out


def _to_bool(series: pd.Series, name: str) -> pd.Series:
    # Exports come as True/False, 0/1 or "true"/"false" depending on the tool. Accept all
    # of them, reject anything else rather than guessing.
    if pd.api.types.is_bool_dtype(series):
        return series
    normalised = series.astype(str).str.strip().str.lower()
    mapping = {"true": True, "1": True, "false": False, "0": False}
    unknown = set(normalised.unique()) - mapping.keys()
    if unknown:
        raise DataValidationError(f"Column {name!r} isn't binary, found values {sorted(unknown)}")
    return normalised.map(mapping).astype(bool)


def cap_outliers(series: pd.Series, quantile: float) -> tuple[pd.Series, CapSummary]:
    """Clip values above a quantile.

    Capping keeps every user in the experiment, which matters because dropping heavy
    players would also change the retention numbers we're testing.
    """
    threshold = float(series.quantile(quantile))
    capped = series.clip(upper=threshold)
    summary = CapSummary(
        column=str(series.name),
        quantile=quantile,
        threshold=threshold,
        n_capped=int((series > threshold).sum()),
        raw_max=float(series.max()),
    )
    logger.info(
        "Capped %d values of %s at %.0f (raw max %.0f)",
        summary.n_capped,
        summary.column,
        threshold,
        summary.raw_max,
    )
    return capped, summary


def split_groups(df: pd.DataFrame, config: Config, column: str) -> tuple[pd.Series, pd.Series]:
    """Return (control, treatment) values for one column."""
    exp = config.experiment
    group = df[exp.group_column]
    return df.loc[group == exp.control, column], df.loc[group == exp.treatment, column]
