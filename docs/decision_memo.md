# Decision Memo: Moving the First Gate to Level 40

**To:** Product Lead, Cookie Cats · **From:** Kaveen Seneviratne · **Date:** [date]

## Recommendation

**[Keep the gate at level 30 / Ship level 40 / Run a follow-up test].** [One sentence: what
happened to 7-day retention, by how much, and how sure we are.]

## What we tested

Players hit a gate that forces them to wait or pay before continuing. We moved it from level 30
to level 40 for a random half of [90,189] new players to see whether a later gate keeps more
people playing. Success was defined in advance as no drop in 7-day retention, with total rounds
played as a guardrail.

## Results

| | Level 30 | Level 40 | Change |
|---|---|---|---|
| Players still active after 7 days | [x]% | [x]% | **[x] pp** (95% CI [x] to [x]) |
| Players still active after 1 day | [x]% | [x]% | [x] pp, not significant |
| Median rounds played | [x] | [x] | [no meaningful change] |

[Insert retention_by_group.png]

In plain terms: [e.g. "for every 1,000 new players, about X fewer are still playing a week
later."] There's a [x]% probability that level 40 is genuinely worse.

## How confident are we?

- The traffic split was checked and [matches the 50/50 design / showed a small imbalance, see
  below].
- The test could reliably detect changes of about [MDE] pp or larger, so [the effect we found
  is within / a smaller effect can't be ruled out].
- A bootstrap and a Bayesian analysis gave the same answer as the main test.

## Risks and what we don't know

- We only see the first week. A later gate might change behaviour further out.
- The gate is a monetisation point and this data has no purchase information. Revenue impact
  could point the other way.
- [Anything specific you found.]

## Next steps

1. [e.g. Keep level 30 as default.]
2. [e.g. If the team still wants a later gate, test level 35 with revenue tracked, sized for an
   MDE of X pp (needs ~N players per group).]
