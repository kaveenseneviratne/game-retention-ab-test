from __future__ import annotations

import pandas as pd
import pytest

from abtest.config import Config
from abtest.data import (
    DataValidationError,
    cap_outliers,
    load_experiment_data,
    split_groups,
    validate,
)


def test_valid_frame_passes(experiment_df: pd.DataFrame, config: Config) -> None:
    out = validate(experiment_df, config)
    assert len(out) == len(experiment_df)
    assert out["retention_7"].dtype == bool


def test_validate_does_not_mutate_input(experiment_df: pd.DataFrame, config: Config) -> None:
    before = experiment_df.copy()
    validate(experiment_df, config)
    pd.testing.assert_frame_equal(experiment_df, before)


def test_missing_column(experiment_df: pd.DataFrame, config: Config) -> None:
    with pytest.raises(DataValidationError, match="Missing required columns"):
        validate(experiment_df.drop(columns="retention_7"), config)


def test_duplicate_users(experiment_df: pd.DataFrame, config: Config) -> None:
    df = pd.concat([experiment_df, experiment_df.head(3)])
    with pytest.raises(DataValidationError, match="duplicated"):
        validate(df, config)


def test_unexpected_group(experiment_df: pd.DataFrame, config: Config) -> None:
    df = experiment_df.copy()
    df.loc[0, "version"] = "gate_99"
    with pytest.raises(DataValidationError, match="Expected groups"):
        validate(df, config)


def test_nulls(experiment_df: pd.DataFrame, config: Config) -> None:
    df = experiment_df.astype({"sum_gamerounds": float})
    df.loc[5, "sum_gamerounds"] = None
    with pytest.raises(DataValidationError, match="Null"):
        validate(df, config)


@pytest.mark.parametrize("encoding", [lambda s: s.astype(int), lambda s: s.astype(str).str.upper()])
def test_binary_encodings_are_accepted(experiment_df, config, encoding) -> None:  # type: ignore[no-untyped-def]
    df = experiment_df.copy()
    df["retention_1"] = encoding(df["retention_1"])
    out = validate(df, config)
    assert out["retention_1"].tolist() == experiment_df["retention_1"].tolist()


def test_non_binary_values_rejected(experiment_df: pd.DataFrame, config: Config) -> None:
    df = experiment_df.astype({"retention_1": object})
    df.loc[0, "retention_1"] = "maybe"
    with pytest.raises(DataValidationError, match="isn't binary"):
        validate(df, config)


def test_negative_guardrail_rejected(experiment_df: pd.DataFrame, config: Config) -> None:
    df = experiment_df.copy()
    df.loc[0, "sum_gamerounds"] = -1
    with pytest.raises(DataValidationError, match="negative"):
        validate(df, config)


def test_cap_outliers_keeps_every_row() -> None:
    s = pd.Series([1, 2, 3, 4, 10_000], name="rounds")
    capped, summary = cap_outliers(s, quantile=0.8)
    assert len(capped) == len(s)
    assert capped.max() == summary.threshold < 10_000
    assert summary.n_capped == 1
    assert summary.raw_max == 10_000


def test_load_reads_csv(experiment_df: pd.DataFrame, config: Config) -> None:
    experiment_df.to_csv(config.data_path, index=False)
    assert len(load_experiment_data(config)) == len(experiment_df)


def test_load_missing_file_has_helpful_message(config: Config) -> None:
    with pytest.raises(FileNotFoundError, match="Kaggle"):
        load_experiment_data(config)


def test_split_groups(experiment_df: pd.DataFrame, config: Config) -> None:
    control, treatment = split_groups(experiment_df, config, "retention_7")
    assert len(control) + len(treatment) == len(experiment_df)
