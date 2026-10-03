from __future__ import annotations

import copy
from pathlib import Path

import pytest

from abtest.config import ConfigError, load_config

PROJECT_CONFIG = Path(__file__).parents[1] / "config" / "experiment.yaml"


def test_project_config_is_valid() -> None:
    config = load_config(PROJECT_CONFIG)
    assert config.metrics.primary == "retention_7"
    assert config.metrics.binary == ("retention_7", "retention_1")


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_missing_section_raises(config_dict, write_config) -> None:  # type: ignore[no-untyped-def]
    del config_dict["metrics"]
    with pytest.raises(ConfigError, match="metrics"):
        load_config(write_config(config_dict))


def test_unknown_key_raises(config_dict, write_config) -> None:  # type: ignore[no-untyped-def]
    config_dict["analysis"]["alhpa"] = 0.05  # typo should not be silently ignored
    with pytest.raises(ConfigError, match="Invalid config"):
        load_config(write_config(config_dict))


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("analysis", "alpha", 1.5),
        ("analysis", "power", 0),
        ("analysis", "guardrail_cap_quantile", 0.3),
        ("analysis", "bootstrap_resamples", 10),
        ("experiment", "treatment", "gate_30"),
        ("metrics", "guardrail", "retention_7"),
    ],
)
def test_invalid_values_raise(config_dict, write_config, section, key, value) -> None:  # type: ignore[no-untyped-def]
    bad = copy.deepcopy(config_dict)
    bad[section][key] = value
    with pytest.raises(ConfigError):
        load_config(write_config(bad))
