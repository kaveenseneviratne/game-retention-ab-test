"""Shared fixtures.

Tests run on synthetic data with known true rates, so we can check the statistics
recover what we put in. The real dataset is never needed to run the suite.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from abtest.config import Config, load_config

CONTROL_RETENTION_7 = 0.19
TREATMENT_RETENTION_7 = 0.18


def make_experiment_frame(
    n_per_group: int = 20_000,
    rates: tuple[float, float] = (CONTROL_RETENTION_7, TREATMENT_RETENTION_7),
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for i, (version, rate) in enumerate(zip(("gate_30", "gate_40"), rates, strict=True)):
        frames.append(
            pd.DataFrame(
                {
                    "userid": np.arange(n_per_group) + i * n_per_group,
                    "version": version,
                    # long right tail, like real engagement data
                    "sum_gamerounds": rng.negative_binomial(1, 0.02, n_per_group),
                    "retention_1": rng.random(n_per_group) < 0.45,
                    "retention_7": rng.random(n_per_group) < rate,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


@pytest.fixture
def experiment_df() -> pd.DataFrame:
    return make_experiment_frame()


@pytest.fixture
def config_dict(tmp_path: Path) -> dict[str, object]:
    return {
        "experiment": {
            "name": "test-experiment",
            "description": "Synthetic data for tests.",
            "control": "gate_30",
            "treatment": "gate_40",
            "group_column": "version",
            "unit_column": "userid",
        },
        "data": {"path": str(tmp_path / "data.csv")},
        "metrics": {
            "primary": "retention_7",
            "secondary": ["retention_1"],
            "guardrail": "sum_gamerounds",
        },
        "analysis": {"bootstrap_resamples": 500, "random_seed": 1},
        "output": {"dir": str(tmp_path / "reports")},
    }


@pytest.fixture
def write_config(tmp_path: Path):  # type: ignore[no-untyped-def]
    def _write(data: dict[str, object]) -> Path:
        path = tmp_path / "experiment.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def config(config_dict: dict[str, object], write_config) -> Config:  # type: ignore[no-untyped-def]
    return load_config(write_config(config_dict))
