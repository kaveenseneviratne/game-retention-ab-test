"""End-to-end: CSV in, reports and figures out."""

from __future__ import annotations

import json

import pandas as pd

from abtest.cli import main
from abtest.config import Config
from abtest.decision import Decision
from abtest.pipeline import run_analysis
from abtest.report import write_reports


def test_full_run_writes_all_outputs(experiment_df: pd.DataFrame, config: Config) -> None:
    experiment_df.to_csv(config.data_path, index=False)

    results = run_analysis(config)
    paths = write_reports(results)

    assert results.srm.passed
    assert results.recommendation.decision is Decision.KEEP_CONTROL  # planted -1 pp drop
    for figure in results.figures.values():
        assert figure.is_file() and figure.stat().st_size > 0

    payload = json.loads(paths["json"].read_text())
    assert payload["recommendation"]["decision"] == "keep control"
    # raw resamples are for plotting only and would bloat the JSON
    assert all("distribution" not in entry for entry in payload["bootstrap"])

    summary = paths["markdown"].read_text()
    assert "Recommendation: KEEP CONTROL" in summary


def test_cli_success(experiment_df: pd.DataFrame, config: Config, tmp_path) -> None:  # type: ignore[no-untyped-def]
    experiment_df.to_csv(config.data_path, index=False)
    out = tmp_path / "cli_reports"
    code = main(["run", "--config", str(tmp_path / "experiment.yaml"), "--output-dir", str(out)])
    assert code == 0
    assert (out / "results.json").is_file()


def test_cli_missing_data_returns_error_code(config: Config, tmp_path) -> None:  # type: ignore[no-untyped-def]
    code = main(["run", "--config", str(tmp_path / "experiment.yaml")])
    assert code == 1
