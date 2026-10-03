from __future__ import annotations

from dataclasses import replace

import pytest

from abtest.decision import Decision, recommend
from abtest.frequentist import ProportionTestResult, RankTestResult
from abtest.quality import SRMResult

SRM_OK = SRMResult({"a": 100, "b": 100}, {"a": 0.5, "b": 0.5}, 0.0, 0.9, 0.001)
SRM_BAD = replace(SRM_OK, p_value=1e-8)

PRIMARY = ProportionTestResult(
    metric="retention_7", control_n=45_000, treatment_n=45_000,
    control_rate=0.19, treatment_rate=0.19, abs_diff=0.0, rel_diff=0.0,
    ci_low=-0.005, ci_high=0.005, z_stat=0.0, p_value=0.8, alpha=0.05,
)  # fmt: skip
GUARDRAIL = RankTestResult(
    metric="sum_gamerounds", control_median=17, treatment_median=17,
    control_mean=50, treatment_mean=50, u_stat=0, p_value=0.6, rank_biserial=0.0, alpha=0.05,
)  # fmt: skip

DROP = replace(PRIMARY, treatment_rate=0.18, abs_diff=-0.01, ci_low=-0.015, ci_high=-0.005,
               p_value=0.001)  # fmt: skip
LIFT = replace(PRIMARY, treatment_rate=0.20, abs_diff=0.01, ci_low=0.005, ci_high=0.015,
               p_value=0.001)  # fmt: skip
GUARDRAIL_WORSE = replace(GUARDRAIL, p_value=0.001, rank_biserial=-0.05)


@pytest.mark.parametrize(
    ("srm", "primary", "guardrail", "expected"),
    [
        (SRM_BAD, LIFT, GUARDRAIL, Decision.INCONCLUSIVE),
        (SRM_OK, DROP, GUARDRAIL, Decision.KEEP_CONTROL),
        (SRM_OK, LIFT, GUARDRAIL, Decision.SHIP_TREATMENT),
        (SRM_OK, LIFT, GUARDRAIL_WORSE, Decision.INCONCLUSIVE),
        (SRM_OK, PRIMARY, GUARDRAIL, Decision.INCONCLUSIVE),
    ],
    ids=["srm-blocks-everything", "drop", "lift", "lift-but-guardrail", "no-effect"],
)
def test_decision_rules(srm, primary, guardrail, expected) -> None:  # type: ignore[no-untyped-def]
    rec = recommend(srm, primary, guardrail, mde=0.008)
    assert rec.decision is expected
    assert rec.reasons


def test_no_effect_mentions_detectable_size() -> None:
    rec = recommend(SRM_OK, PRIMARY, GUARDRAIL, mde=0.008)
    assert any("0.80 pp" in reason for reason in rec.reasons)
