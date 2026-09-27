"""Mastery decay for review ranking (research.md §1, Constitution Principle I).

Fixed global parameters, not per-topic/per-learner-fitted -- same
rationale as `bkt.py`'s own fixed parameters: no real learner data
exists yet to fit against (Constitution Principle VIII). Read-time only
-- this module never writes to `MasteryState` and its output is never
fed back into `apply_bkt_update` (data-model.md). It is used solely to
re-rank the Sequencing Agent's existing mastered-topic review-fallback
pool (`backend/src/agents/sequencing/agent.py`).
"""

import datetime

GRACE_PERIOD = datetime.timedelta(days=21)
HALF_LIFE = datetime.timedelta(days=45)


def effective_mastery_for_review(
    p_mastery: float, *, updated_at: datetime.datetime, now: datetime.datetime
) -> float:
    """Returns `p_mastery` decayed by elapsed time since `updated_at`,
    for review-ranking purposes only (data-model.md's formula). Pure
    and deterministic: identical inputs always produce an identical
    output (FR-010). No decay within `GRACE_PERIOD`; an exponential
    (Ebbinghaus-style) decay with half-life `HALF_LIFE` afterward.
    """
    elapsed = now - updated_at
    if elapsed <= GRACE_PERIOD:
        return p_mastery

    elapsed_after_grace = elapsed - GRACE_PERIOD
    return p_mastery * 0.5 ** (elapsed_after_grace / HALF_LIFE)
