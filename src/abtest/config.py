"""Load and validate the experiment config.

The YAML file is the pre-registered analysis plan. Parsing it into frozen dataclasses
means the rest of the code gets typed, immutable settings instead of a loose dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the config is missing fields or contains invalid values."""


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    control: str
    treatment: str
    group_column: str
    unit_column: str
    description: str = ""


@dataclass(frozen=True)
class MetricSpec:
    primary: str
    guardrail: str
    secondary: tuple[str, ...] = ()

    @property
    def binary(self) -> tuple[str, ...]:
        """All conversion-style metrics, primary first."""
        return (self.primary, *self.secondary)


@dataclass(frozen=True)
class AnalysisSpec:
    alpha: float = 0.05
    power: float = 0.80
    srm_alpha: float = 0.001
    bootstrap_resamples: int = 10_000
    random_seed: int = 42
    guardrail_cap_quantile: float = 0.9999


@dataclass(frozen=True)
class Config:
    experiment: ExperimentSpec
    metrics: MetricSpec
    analysis: AnalysisSpec
    data_path: Path
    output_dir: Path


def load_config(path: str | Path) -> Config:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    try:
        metrics_raw = raw["metrics"]
        config = Config(
            experiment=ExperimentSpec(**raw["experiment"]),
            metrics=MetricSpec(
                primary=metrics_raw["primary"],
                guardrail=metrics_raw["guardrail"],
                secondary=tuple(metrics_raw.get("secondary") or ()),
            ),
            analysis=AnalysisSpec(**(raw.get("analysis") or {})),
            data_path=Path(raw["data"]["path"]),
            output_dir=Path((raw.get("output") or {}).get("dir", "reports")),
        )
    except KeyError as exc:
        raise ConfigError(f"Missing required config key: {exc}") from exc
    except TypeError as exc:
        # dataclass constructors raise TypeError on unknown or missing keyword args
        raise ConfigError(f"Invalid config section: {exc}") from exc

    _validate(config)
    return config


def _validate(config: Config) -> None:
    exp, an = config.experiment, config.analysis

    if exp.control == exp.treatment:
        raise ConfigError("Control and treatment must be different groups.")
    for name, value in (("alpha", an.alpha), ("power", an.power), ("srm_alpha", an.srm_alpha)):
        if not 0 < value < 1:
            raise ConfigError(f"analysis.{name} must be between 0 and 1, got {value}.")
    if not 0.5 < an.guardrail_cap_quantile <= 1:
        raise ConfigError("analysis.guardrail_cap_quantile must be in (0.5, 1].")
    if an.bootstrap_resamples < 100:
        raise ConfigError("analysis.bootstrap_resamples should be at least 100.")
    if config.metrics.guardrail in config.metrics.binary:
        raise ConfigError("The guardrail metric cannot also be a binary metric.")
