"""Write analysis results to disk: a machine-readable JSON and a readable Markdown summary.

The JSON is the source of truth for anything downstream (a dashboard, a CV bullet, the
memo). The Markdown is for humans skimming the repo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from abtest import __version__
from abtest.pipeline import AnalysisResults


def write_reports(results: AnalysisResults) -> dict[str, Path]:
    out_dir = results.config.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "results.json"
    json_path.write_text(json.dumps(to_dict(results), indent=2), encoding="utf-8")

    md_path = out_dir / "summary.md"
    md_path.write_text(render_markdown(results), encoding="utf-8")

    return {"json": json_path, "markdown": md_path}


def to_dict(results: AnalysisResults) -> dict[str, Any]:
    payload = {
        "meta": {
            "experiment": results.config.experiment.name,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "package_version": __version__,
            "n_users": results.n_users,
        },
        "recommendation": results.recommendation,
        "srm": {**asdict(results.srm), "passed": results.srm.passed},
        "outlier_cap": results.cap,
        "power": results.power,
        "primary": {**asdict(results.primary), "significant": results.primary.significant},
        "secondary": [{**asdict(r), "significant": r.significant} for r in results.secondary],
        "guardrail": {**asdict(results.guardrail), "significant": results.guardrail.significant},
        "bootstrap": [results.bootstrap_primary, results.bootstrap_guardrail],
        "bayesian": results.bayesian,
        "figures": {name: path.as_posix() for name, path in results.figures.items()},
    }
    cleaned: dict[str, Any] = _clean(payload)
    return cleaned


def _clean(obj: Any) -> Any:
    """Recursively convert dataclasses, enums and numpy types into plain JSON values."""
    if is_dataclass(obj) and not isinstance(obj, type):
        # Raw bootstrap samples are large and only needed for plotting.
        return {k: _clean(v) for k, v in asdict(obj).items() if k != "distribution"}
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k != "distribution"}
    if isinstance(obj, list | tuple):
        return [_clean(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def _pct(x: float) -> str:
    return f"{x:.2%}"


def _pp(x: float) -> str:
    return f"{100 * x:+.2f} pp"


def render_markdown(results: AnalysisResults) -> str:
    exp = results.config.experiment
    rec, srm, power = results.recommendation, results.srm, results.power
    binary = [results.primary, *results.secondary]

    lines = [
        f"# Results: {exp.name}",
        "",
        f"_{exp.description}_  ",
        f"Control: `{exp.control}` · Treatment: `{exp.treatment}` · "
        f"Users analysed: {results.n_users:,}",
        "",
        f"## Recommendation: {rec.decision.value.upper()}",
        "",
        *[f"- {reason}" for reason in rec.reasons],
        "",
        "## Experiment health",
        "",
        f"- Sample ratio check: {'passed' if srm.passed else '**FAILED**'} "
        f"(observed {srm.observed}, p = {srm.p_value:.3f})",
        f"- Guardrail outliers: {results.cap.n_capped} values capped at "
        f"{results.cap.threshold:,.0f} (raw max {results.cap.raw_max:,.0f})",
        f"- Minimum detectable effect at {results.config.analysis.power:.0%} power: "
        f"{100 * power.mde:.2f} pp on a {_pct(power.baseline)} baseline",
        "",
        "## Retention",
        "",
        "| Metric | Role | Control | Treatment | Difference | 95% CI | p-value | Adj. p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(binary):
        role = "primary" if i == 0 else "secondary"
        adj = "n/a" if r.p_value_adjusted is None else f"{r.p_value_adjusted:.4f}"
        lines.append(
            f"| {r.metric} | {role} | {_pct(r.control_rate)} | {_pct(r.treatment_rate)} | "
            f"{_pp(r.abs_diff)} ({r.rel_diff:+.1%}) | {_pp(r.ci_low)} to {_pp(r.ci_high)} | "
            f"{r.p_value:.4f} | {adj} |"
        )

    g, bp, bg, bayes = (
        results.guardrail,
        results.bootstrap_primary,
        results.bootstrap_guardrail,
        results.bayesian,
    )
    lines += [
        "",
        "## Guardrail",
        "",
        f"- Median rounds: {g.control_median:.0f} (control) vs {g.treatment_median:.0f} "
        f"(treatment); bootstrap 95% CI for the difference {bg.ci_low:+.1f} to {bg.ci_high:+.1f}",
        f"- Mann-Whitney U p = {g.p_value:.4f}, rank-biserial r = {g.rank_biserial:+.3f}",
        "",
        "## Robustness checks",
        "",
        f"- Bootstrap ({bp.n_resamples:,} resamples) 95% CI for {bp.metric}: "
        f"{_pp(bp.ci_low)} to {_pp(bp.ci_high)}; share of resamples below zero "
        f"{bp.prob_below_zero:.1%}",
        f"- Bayesian: P(treatment better) = {bayes.prob_treatment_better:.1%}; expected loss "
        f"if we ship treatment = {100 * bayes.expected_loss_treatment:.3f} pp",
        "",
        "## Figures",
        "",
        *[f"![{name}](figures/{path.name})" for name, path in results.figures.items()],
        "",
        f"<sub>Generated by abtest {__version__}. Do not edit by hand; rerun `make analyse`.</sub>",
        "",
    ]
    return "\n".join(lines)
