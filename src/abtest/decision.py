"""Turn test results into a recommendation using the rules fixed in the analysis plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from abtest.frequentist import ProportionTestResult, RankTestResult
from abtest.quality import SRMResult


class Decision(StrEnum):
    SHIP_TREATMENT = "ship treatment"
    KEEP_CONTROL = "keep control"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Recommendation:
    decision: Decision
    reasons: list[str] = field(default_factory=list)


def recommend(
    srm: SRMResult,
    primary: ProportionTestResult,
    guardrail: RankTestResult,
    mde: float,
) -> Recommendation:
    if not srm.passed:
        return Recommendation(
            Decision.INCONCLUSIVE,
            [
                f"Sample ratio mismatch (p = {srm.p_value:.2g}). The split doesn't match the "
                "design, so effect estimates aren't trustworthy until the cause is found."
            ],
        )

    pp = 100 * primary.abs_diff
    ci = f"95% CI {100 * primary.ci_low:+.2f} to {100 * primary.ci_high:+.2f} pp"

    if primary.significant and primary.abs_diff < 0:
        return Recommendation(
            Decision.KEEP_CONTROL,
            [f"{primary.metric} dropped by {abs(pp):.2f} pp in treatment ({ci})."],
        )

    if primary.significant and primary.abs_diff > 0:
        if guardrail.significant and guardrail.rank_biserial < 0:
            return Recommendation(
                Decision.INCONCLUSIVE,
                [
                    f"{primary.metric} improved by {pp:.2f} pp ({ci}), but the guardrail "
                    f"{guardrail.metric} got worse. Needs a judgement call on the trade-off.",
                ],
            )
        return Recommendation(
            Decision.SHIP_TREATMENT,
            [f"{primary.metric} improved by {pp:.2f} pp ({ci}) with the guardrail intact."],
        )

    return Recommendation(
        Decision.INCONCLUSIVE,
        [
            f"No significant change in {primary.metric} ({pp:+.2f} pp, {ci}).",
            f"The test could reliably detect drops of about {100 * mde:.2f} pp or more, so "
            "an effect smaller than that can't be ruled out.",
        ],
    )
