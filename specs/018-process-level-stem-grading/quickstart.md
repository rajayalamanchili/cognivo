# Quickstart: Process-Level STEM Grading

**Feature**: `018-process-level-stem-grading` | **Date**: 2026-09-14

Validates all three user stories end to end against a real dev
database. Prerequisites: Milestones 1 and 6 already deployed/runnable
locally, `DATABASE_URL` reachable, `GRADING_AGENT_URL` +
`GRADING_AGENT_SHARED_SECRET` set, and `algebra-1`'s content artifact
authored with `process_level_grading: true` on at least one topic
(research.md §5). `biology` is left untouched, so it doubles as the
SC-003 regression fixture.

## Setup

```bash
cd backend
alembic upgrade head            # applies this feature's step_grading_enabled migration
python scripts/load_content_artifact.py content/algebra-1/subject.yaml
python scripts/load_content_artifact.py content/biology/subject.yaml
```

## Scenario 1 -- User Story 1: a wrong step is named, not just "incorrect" (SC-001, SC-002)

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/next-question?subject_id=algebra-1&topic_id=linear-equations"
```

**Expected**: `question_type: "multi_step"`, `options: null`,
`answer_key` not present in the response (never sent to the client,
unchanged existing behavior), but the question's step prompts are --
confirm the returned shape carries an ordered list of per-step prompts
the learner is meant to answer.

```bash
curl -s -X POST "$BACKEND_URL/api/questions/<question_id>/answer" \
  -H "Content-Type: application/json" \
  -d '{"response": ["Subtract 2 from both sides: 3x = 12", "Divide both sides by 5: x = 2.4"]}'
```

**Expected**: `correct: false`, `first_diverging_step_index: 1`,
`step_results` has exactly two entries (step 0 correct, step 1
incorrect -- the learner divided by 5 instead of 3) -- naming the wrong
step, not a bare `"incorrect"` (SC-001). Re-submitting the identical
`response` to a second, disposable question with the same rubric
produces byte-identical `step_results` (SC-002).

Inspect the audit log directly (no dedicated audit-log endpoint
exists, same convention prior quickstarts use):

```sql
SELECT payload FROM assessment_events
WHERE event_type = 'answer_submitted' AND question_id = '<question_id>'
ORDER BY created_at DESC LIMIT 1;
```

**Expected**: `payload.first_diverging_step_index = 1`,
`payload.step_results[1].criteria_missed` names the specific rubric
criterion the step failed -- this is FR-008's "reconstructable after
the fact" requirement and User Story 2's Acceptance Scenario 2.

## Scenario 2 -- User Story 1: an all-correct submission behaves like any other correct answer

```bash
curl -s -X POST "$BACKEND_URL/api/questions/<new_question_id>/answer" \
  -H "Content-Type: application/json" \
  -d '{"response": ["Subtract 2 from both sides: 3x = 12", "Divide both sides by 3: x = 4"]}'
```

**Expected**: `correct: true`, `first_diverging_step_index: null`,
`step_results` has one entry per step, all `correct: true`, and
`posterior_p_mastery` moves exactly the same way it would for any other
correct answer to this topic (Acceptance Scenario 2).

## Scenario 3 -- User Story 3: step-count mismatch is rejected before grading (FR-012)

```bash
curl -s -X POST "$BACKEND_URL/api/questions/<question_id>/answer" \
  -H "Content-Type: application/json" \
  -d '{"response": ["Subtract 2 from both sides: 3x = 12"]}'
```

**Expected**: `422`, `{"error": "step_count_mismatch", "expected_step_count": 2, "submitted_step_count": 1}`.
Confirm no `ANSWER_SUBMITTED` event was written and the question
remains answerable:

```sql
SELECT event_type FROM assessment_events
WHERE question_id = '<question_id>' ORDER BY created_at DESC LIMIT 1;
-- expect: step_count_mismatch_rejected, not answer_submitted
```

## Scenario 4 -- User Story 3: an unopted-in topic is untouched (SC-003)

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/next-question?subject_id=biology&topic_id=cell-structure"
```

**Expected**: `question_type` is `multiple_choice`/`numeric`/`free_text`
only, never `multi_step` -- `biology` authored no
`process_level_grading` topics, so `step_grading_enabled` is `false`
for all of it. Run Milestones 1 and 6's existing acceptance suites
against this same database and confirm 100% pass, unmodified (SC-003).

## Scenario 5 -- User Story 3: the Grading Agent's step logic redeploys alone (SC-005)

Deploy a scoring-logic change to `grading-agent/` only (e.g. a rubric-
matching prompt tweak), redeploy that service alone, and re-run
Scenario 1. **Expected**: the new step-level result reflects the
change; `backend`'s and `frontend`'s deployments are untouched --
confirms this feature preserved Milestone 6's existing A2A
independent-redeploy guarantee (Constitution Principle VI) rather than
eroding it.
