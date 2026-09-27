# Quickstart: Spaced Repetition / Mastery Decay for Foundational Topics

**Feature**: `024-mastery-decay` | **Date**: 2026-09-27

Validates both user stories against a real dev database. No new API
endpoint exists (research.md §4) -- this feature changes the internal
ordering of two existing endpoints' fallback path
(`GET /api/learners/{learner_id}/topic-priority-preview` and
`GET /api/learners/{learner_id}/next-question`), so validation reuses
those plus direct SQL to simulate elapsed time, since a 21-day grace
period + 45-day half-life can't be waited out in a quickstart. This
mirrors `specs/017-grade-banded-curriculum/quickstart.md`'s existing
precedent of inspecting real database state directly where no
dedicated endpoint exists for what needs verifying.

## Setup

```bash
cd backend
alembic upgrade head   # no new migration ships with this feature -- confirms zero drift
```

Use the seeded demo learner and `algebra-1` (any subject with at least
two topics whose prerequisites can both be exhausted works). Answer
enough questions correctly on two topics, `<topic-a>` and `<topic-b>`,
that both reach the `mastered` band, and exhaust every other topic's
eligibility (either by mastering everything else too, or using a
subject/content fixture small enough that only these two remain).

## Scenario 1 -- User Story 1: a long-untouched mastered topic is reviewed first (SC-001)

Confirm both topics are mastered with comparable `p_mastery`:

```sql
SELECT topic_id, p_mastery, updated_at
FROM mastery_states
WHERE learner_id = '<demo-learner-id>' AND subject_id = 'algebra-1'
  AND topic_id IN ('<topic-a>', '<topic-b>');
```

Backdate one of them well past the decay grace period + half-life
(`GRACE_PERIOD` = 21 days, `HALF_LIFE` = 45 days per `backend/src/
services/mastery/decay.py` -- backdating 90 days clears both):

```sql
UPDATE mastery_states
SET updated_at = now() - interval '90 days'
WHERE learner_id = '<demo-learner-id>' AND subject_id = 'algebra-1'
  AND topic_id = '<topic-a>';
```

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/topic-priority-preview?subject_id=algebra-1"
```

**Expected**: `is_fallback` is `true` (both topics mastered, nothing
else eligible), and `next_topic.topic_id` is `<topic-a>` -- the
backdated, more-decayed topic -- even though `next_topic.p_mastery` in
the response still shows `<topic-a>`'s **raw**, undecayed value
(FR-005: the displayed number never reflects decay, only the ordering
does). Re-run the same request again: the result is identical
(SC-004's reproducibility guarantee).

*(Optional regression check, do this instead of continuing to Scenario
2: revert the backdate -- `UPDATE mastery_states SET updated_at =
now() WHERE ... topic_id = '<topic-a>'` -- and confirm the fallback
pick reverts to whichever topic's* raw *`p_mastery` is lower between
the two, proving decay only changes ordering when it's actually decayed
something. This is SC-002's "zero change within the grace period" from
the other direction.)*

## Scenario 2 -- User Story 2: answering a decayed topic updates mastery normally (SC-003)

With `<topic-a>` still backdated from Scenario 1, fetch the actual next
question (the same fallback pick, but generating a real question this
time rather than just previewing it):

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/next-question?subject_id=algebra-1"
```

**Expected**: the returned `question_id` is for `<topic-a>` (same
fallback pick as Scenario 1). Answer it:

```bash
curl -s -X POST "$BACKEND_URL/api/questions/<question_id>/answer" \
  -H "Content-Type: application/json" \
  -d '{"response": ...}'
```

**Expected**: the response's `prior_p_mastery` equals `<topic-a>`'s
**raw**, pre-backdate `p_mastery` exactly (never a decayed number), and
`posterior_p_mastery` matches exactly what `apply_bkt_update` would
produce from that raw prior -- confirm via:

```sql
SELECT p_mastery, updated_at FROM mastery_states
WHERE learner_id = '<demo-learner-id>' AND subject_id = 'algebra-1'
  AND topic_id = '<topic-a>';
```

`updated_at` is now `now()` again (decay has restarted from this fresh
answer). No special-cased response field, no new payload key -- the
shape is identical to answering any other topic.

## Automated coverage

All of the above is also covered without a live server or manual SQL,
per `plan.md`'s Testing section:

```bash
cd backend
uv run pytest tests/unit/test_mastery_decay.py tests/unit/test_topic_priority_decay.py tests/integration/test_next_topic_decay_fallback.py tests/integration/test_decayed_topic_answer_unaffected.py -v
```
