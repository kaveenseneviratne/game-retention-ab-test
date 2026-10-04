# Decision Memo: Moving the First Gate to Level 40

**To:** Product Lead, Cookie Cats · **From:** Kaveen Seneviratne · **Date:** 3 October 2026

## Recommendation

**Keep the gate at level 30.** Moving it to level 40 reduced the share of players still active
after a week by 0.82 percentage points (from 19.0% to 18.2%), and we are confident this drop is real.

## What we tested

Players hit a gate that forces them to wait or pay before continuing. We moved it from level 30
to level 40 for a random half of 90,189 new players to see whether a later gate keeps more people
playing. Success was defined in advance as no drop in 7-day retention, with total rounds played
as a guardrail.

## Results

| | Level 30 | Level 40 | Change |
|---|---|---|---|
| Players still active after 7 days | 19.02% | 18.20% | **−0.82 pp** (95% CI −1.33 to −0.31) |
| Players still active after 1 day | 44.82% | 44.23% | −0.59 pp, not significant |
| Median rounds played | 17 | 16 | No meaningful change |

![Retention by group](images/retention_by_group.png)

In plain terms: **for every 1,000 new players, about 8 fewer are still playing a week later**
with the gate at level 40. Across the 45,000 players in the test group, that's roughly 370
players lost. There is a 99.9% probability that level 40 is genuinely worse.

## How confident are we?

- **The result is statistically clear** (p = 0.002), and two independent methods, a bootstrap
  and a Bayesian analysis, gave the same answer.
- **The test was large enough.** It could reliably detect drops of 0.73 pp or more, and the drop
  we found is bigger than that.
- **One flag on the traffic split.** Level 40 received 789 more players than level 30 (50.4% vs
  49.6%). That passes our pre-agreed threshold, but it's a larger imbalance than chance usually
  produces (p = 0.009). It's too small to explain the result, but it's worth checking how players
  were assigned before the next test.

## Risks and what we don't know

- **We only see the first week.** Longer-term retention could look different.
- **No revenue data.** The gate is also where players can pay to continue. Moving it later might
  change purchase behaviour in ways this test can't measure, and that could change the trade-off.
- **Why it happened is a hypothesis, not a finding.** One plausible explanation is that an earlier
  forced break keeps the game feeling fresh, while a later one comes after players are already
  tiring of it. This data can't confirm that.

## Next steps

1. **Keep the gate at level 30** as the default.
2. **Check the assignment process** to understand the small traffic imbalance before running
   another test.
3. **If the team still wants a later gate,** test a smaller move (e.g. level 35) with purchase data
   tracked. To detect a 0.5 pp change reliably, that test needs about 96,000 players per group,
   roughly double this one.
