# Data Model: Spaced Repetition / Mastery Decay for Foundational Topics

**Feature**: `024-mastery-decay` | **Date**: 2026-09-27

No new tables, no modified tables, no new columns, no new
`AssessmentEventType` value, no Alembic migration (research.md §4).
This feature's only "data" is a computed, never-persisted value derived
from an already-existing column.

## Computed value: Effective Mastery (for review ranking)

Not a database column, not an ORM attribute, not a new entity with its
own lifecycle -- a pure function's return value, computed fresh on
every ranking call and discarded immediately after use.

**Inputs** (all already available to `rank_eligible_topics`'s callers
before this feature):

| Input | Source | Notes |
|---|---|---|
| `p_mastery` | `MasteryState.p_mastery` | The existing, evidence-based BKT posterior. Never modified by this feature. |
| `updated_at` | `MasteryState.updated_at` | Already a column (`onupdate=func.now()`); newly *read* by the ranking path, not newly added. |
| `now` | `datetime.datetime.now(datetime.UTC)`, captured once per `select_next_topic`/`preview_topic_priority` call | Not stored anywhere; exists only for the duration of one ranking call (FR-010). |

**Formula** (`backend/src/services/mastery/decay.py`):

```
elapsed = now - updated_at
if elapsed <= GRACE_PERIOD:                       # GRACE_PERIOD = 21 days
    effective_p_mastery = p_mastery
else:
    elapsed_after_grace = elapsed - GRACE_PERIOD
    effective_p_mastery = p_mastery * 0.5 ** (elapsed_after_grace / HALF_LIFE)  # HALF_LIFE = 45 days
```

`GRACE_PERIOD` and `HALF_LIFE` are fixed global constants (FR-009),
defined once in `decay.py`, analogous to `bkt.py`'s `P_L0`/`P_T`/`P_S`/
`P_G_*`. See research.md §1 for the values' rationale.

**Where it's used**: exclusively inside `rank_eligible_topics`'s sort
key, and only for a topic whose `band_by_topic[topic_id] == "mastered"`
(research.md §2). Never computed for a topic with no `MasteryState` row
(FR-007 -- "unknown" stays "unknown"), never computed for a topic in
`"struggling"`/`"developing"` band (those are never in the mastered
pool to begin with).

**Where it is NOT used** (FR-002, FR-005 -- enforced by never wiring it
in anywhere else, not by a guard clause):
- `MasteryState.p_mastery`, `update_count`, `consecutive_mastered_
  observations` -- never written.
- `apply_bkt_update` (`backend/src/services/mastery/bkt.py`) -- never
  called with a decayed value as its prior; `apply_mastery_update`
  (`mastery_tool.py`) already only ever reads `existing.p_mastery`
  (raw), and this feature does not touch that file at all.
- `MasteryBand`/`mastery_band_for` -- band classification is a pure
  function of raw `p_mastery` and `consecutive_mastered_observations`
  only; this feature adds no second band-computation path.
- `TopicPreviewEntryOut.p_mastery` (the dashboard preview's displayed
  value) -- sourced from `ctx.p_mastery_by_topic` (raw), unchanged.
- The Recommendation Agent's weak-area report (`weak_area.py`) -- calls
  `mastery_band_for` directly on raw `p_mastery`, never goes through
  `rank_eligible_topics` at all, so it is unaffected without any
  explicit exclusion needed.

## Modified function signature: `rank_eligible_topics`

`backend/src/agents/sequencing/agent.py`. Two new optional keyword
arguments, both defaulting to `None` (research.md §2):

| Parameter | Type | Default | Effect when omitted |
|---|---|---|---|
| `updated_at_by_topic` | `dict[str, datetime.datetime] \| None` | `None` | Every topic's effective mastery equals its raw `p_mastery` -- byte-identical to pre-feature behavior. |
| `now` | `datetime.datetime \| None` | `None` | Same as above. |

Return type and every other parameter are unchanged. All five existing
call sites in the test suite that omit these two new parameters
continue to exercise the exact pre-feature code path.

## Modified dataclass: `_TopicRankingContext`

`backend/src/agents/sequencing/agent.py`. One new field:

| Field | Type | Notes |
|---|---|---|
| `updated_at_by_topic` | `dict[str, datetime.datetime]` | Populated by `_load_topic_ranking_context` from the same `MasteryState` query it already runs -- no new query. A topic with no `MasteryState` row has no entry (consistent with `p_mastery_by_topic`'s existing `None`-for-absent convention, though here the key is simply absent rather than mapped to `None`, since a missing `updated_at` is never a meaningful value to decay from). |
