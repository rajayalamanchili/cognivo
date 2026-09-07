# Quickstart: Grade-Banded Curriculum Scoping

**Feature**: `017-grade-banded-curriculum` | **Date**: 2026-09-06

Validates all three user stories end to end against a real dev database.
Prerequisites: Milestone 1 already deployed/runnable locally,
`DATABASE_URL` reachable, and `algebra-1`'s content artifact authored
with `grade_bands` + a per-topic `grade` on every topic (a `tasks.md`
item -- this feature has nothing to demo against an ungraded subject by
design, per FR-009/SC-005). `biology` is deliberately left ungraded, so
it doubles as the SC-005 regression fixture.

## Setup

```bash
cd backend
alembic upgrade head            # applies both of this feature's migrations
python scripts/load_content_artifact.py content/algebra-1/subject.yaml
python scripts/load_content_artifact.py content/biology/subject.yaml
```

## Scenario 1 -- User Story 1: placement also finds a starting grade (SC-001, SC-006)

```bash
curl -s -X POST "$BACKEND_URL/api/subjects/algebra-1/placement/start"
```

**Expected**: `questions` spans more than one distinct `grade` value,
each question carries a non-null `grade`. Note each `question_id` and
its `grade`.

```bash
curl -s -X POST "$BACKEND_URL/api/placement/<placement_session_id>/submit" \
  -H "Content-Type: application/json" \
  -d '{"answers": [{"question_id": "<id>", "response": ...}, ...]}'
```

**Expected**: `mastery_state` in the response is unchanged in shape from
today. Then inspect the audit log directly (no dedicated audit-log
endpoint exists -- same convention `specs/015-semantic-caching/quickstart.md`
already uses):

```sql
SELECT payload FROM assessment_events
WHERE event_type = 'grade_assigned' AND learner_id = '<demo-learner-id>'
ORDER BY created_at DESC LIMIT 1;
```

**Expected**: one `grade_assigned` event, `payload.starting_grade` set,
`payload.correct_by_grade` showing exactly which grades' questions were
answered correctly -- this is SC-006's "reconstruct why" requirement and
Acceptance Scenario 4's "state which answers drove that placement."
Re-running this scenario against a second, disposable learner with the
identical answer sequence produces the identical `starting_grade`
(SC-001) -- the unit test for `determine_starting_grade` (`research.md`
Decision 3) covers the ten-repeated-runs form of this check directly,
with no DB involved.

## Scenario 2 -- User Story 3: skip a too-high placement question (SC-004)

Start a fresh placement session, then skip a question whose `grade` is
above the lowest grade shown:

```bash
curl -s -X POST "$BACKEND_URL/api/placement/<placement_session_id>/skip" \
  -H "Content-Type: application/json" \
  -d '{"question_id": "<the-higher-grade-question-id>"}'
```

**Expected**: `replacement_question` is non-null, its `grade` is at or
below the interim currently-assessed level, and it targets a topic not
already present in this session's question set -- one round-trip, no
call to `/placement/start` again (SC-004).

```bash
curl -s -X POST "$BACKEND_URL/api/placement/<placement_session_id>/skip" \
  -H "Content-Type: application/json" \
  -d '{"question_id": "<the-lowest-grade-question-id>"}'
```

**Expected**: `422` -- the lowest-grade question was never above the
interim level, so it was never eligible to skip.

Submit the session with the skipped question's `question_id` omitted
from `answers` entirely. **Expected**: the skipped question's topic
reports `status: "unknown"` in the response (FR-007), and placement
still completes with a valid `starting_grade` in the audit log (FR-008).

## Scenario 3 -- User Story 2: progressive grade unlocking (SC-002, SC-003)

Using the learner placed in Scenario 1, drive every topic in their
starting grade to the "mastered" band except one (submit correct
answers via `/api/questions/{id}/answer` for every topic but one in
that grade):

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/next-question?subject_id=algebra-1"
```

**Expected**: every returned `topic_id` still belongs to the starting
grade or lower -- never a higher grade (SC-002), confirmed across
repeated calls while the one topic remains unmastered (SC-003).

Now bring that last topic to "mastered" (two consecutive correct
answers, per the existing `MASTERY_CONFIRMATION_THRESHOLD`):

```sql
SELECT payload FROM assessment_events
WHERE event_type = 'grade_unlocked' AND learner_id = '<demo-learner-id>'
ORDER BY created_at DESC LIMIT 1;
```

**Expected**: a `grade_unlocked` event appears, `payload.new_unlocked_grade`
is exactly one above the previous value. The next
`GET .../next-question` call may now select a topic from the newly
unlocked grade (subject to that grade's own prerequisites, unchanged).

If the starting grade was already the subject's highest declared grade,
mastering it produces no `grade_unlocked` event and every subsequent
`next-question` call keeps selecting from that same top grade
(Acceptance Scenario 3 of User Story 2) -- no error, no attempt to
unlock a nonexistent grade.

## Regression

```bash
cd backend && pytest
cd ../frontend && npm test
```

**Expected**: `biology`'s entirely ungraded placement/practice flow
(`test_placement.py`'s existing Milestone 1 scenarios run against
`biology`) passes completely unmodified -- SC-005.
