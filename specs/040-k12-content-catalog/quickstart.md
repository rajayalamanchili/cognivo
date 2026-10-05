# Quickstart: Full K-12 Content Catalog

**Feature**: `040-k12-content-catalog` | **Date**: 2026-10-04

Validates all three user stories against a real dev database. No
migration ships with this feature — `alembic upgrade head` should be a
no-op; only new content-artifact *rows* are written via the existing
loader script. Reuses the seeded demo learner and the existing
placement/practice/quiz-assignment/instructor-dashboard flows.

## Setup

```bash
cd backend
# confirm no pending migration (this feature adds none)
alembic current  # should already equal alembic heads

python scripts/load_content_artifact.py content/algebra-2/subject.yaml
python scripts/load_content_artifact.py content/physics/subject.yaml
python scripts/check_no_subject_conditionals.py   # must stay clean (FR-007)
```

**Expected**: both loads exit `0`; `check_no_subject_conditionals.py`
reports no violations — confirming zero engine code branches on
`subject_id in {"algebra-2", "physics"}` or any new conditional at all.

## Scenario 1 — User Story 3: new subjects pass the existing content gate (SC-002)

```sql
SELECT subject_id, COUNT(*) AS topic_count
FROM topics WHERE subject_id IN ('algebra-2', 'physics')
GROUP BY subject_id;
-- expect: algebra-2 = 8, physics = 8

SELECT subject_id, topic_id FROM topics
WHERE subject_id IN ('algebra-2', 'physics')
  AND (skill_definition IS NULL OR career_connection IS NULL);
-- expect: zero rows (every topic has both)

SELECT t.subject_id, t.topic_id FROM topics t
LEFT JOIN (
  SELECT subject_id, topic_id, COUNT(*) AS n FROM standards_tags
  GROUP BY subject_id, topic_id
) s ON s.subject_id = t.subject_id AND s.topic_id = t.topic_id
WHERE t.subject_id IN ('algebra-2', 'physics') AND (s.n IS NULL OR s.n = 0);
-- expect: zero rows (every topic carries at least one real standards tag)
```

Then confirm rejection still works, without touching either new file
permanently: temporarily edit one topic in a scratch copy of
`content/algebra-2/subject.yaml` to add a `prerequisites` entry naming a
topic that doesn't exist in that subject, and re-run the loader against
the scratch copy.

**Expected**: load fails with the same "unknown prerequisite" error class
Algebra I/Biology already produce — no new error type, confirming
research.md Decision 2 (prerequisites remain same-subject-only).

## Scenario 2 — User Story 1: learner can select and work through a new subject (SC-001, SC-003)

Placement has no `learner_id` parameter at all -- it always resolves to
the single seeded demo learner (`services/demo_learner.get_demo_learner`,
Milestone 1):

```bash
curl -s -X POST "$BACKEND_URL/api/subjects/algebra-2/placement/start"
```

**Expected**: placement starts and returns a first question exactly as it
would for `subject_id: "algebra-1"` — same response shape, same
behavior. Answer each question via `POST /api/placement/{placement_session_id}/submit`,
then read mastery state:

```bash
curl -s "$BACKEND_URL/api/learners/<demo_learner_id>/mastery-state?subject_id=algebra-2"
```

**Expected**: mastery state reflects the Sequencing Agent's standard BKT
update, identical in shape to an Algebra I/Biology mastery-state read.
Repeat both calls with `subject_id: physics` to confirm the same holds
for the second new subject. (Live-verified 2026-10-05, T015 -- see Live
Validation Results below.)

## Scenario 3 — User Story 2: instructor can assign and review a new subject (SC-004), plus FR-009

As an authenticated instructor with a roster already created for
`physics` (`POST /api/rosters`, optionally declaring `grade`):

```bash
curl -s -X POST "$BACKEND_URL/api/rosters/<roster_id>/assignments" \
  -H "Content-Type: application/json" \
  -d '{"topic_ids": ["kinematics-motion-in-one-dimension"], "question_count": 1, "learner_ids": "all"}'
```

**Expected**: assignment creation succeeds with `physics` selectable
exactly as `algebra-1`/`biology` already are — no new field, no new
error path. Have a guardian complete the assignment on a targeted
learner's behalf (`POST /api/assignments/{assignment_id}/learners/{learner_id}/start`,
then `POST /api/questions/{question_id}/answer`), then:

```bash
curl -s "$BACKEND_URL/api/rosters/<roster_id>/assignments/<assignment_id>"
```

**Expected**: per-learner status/score renders identically to an
Algebra I/Biology assignment report. Separately (FR-009, found during
`/speckit-implement`): `POST /api/rosters` with `{"subject_id": "physics", "grade": 8}`
is rejected `422` (physics declares `grade_bands: [9, 10, 11]`); the same
call with `grade: 9` succeeds. (Live-verified 2026-10-05, T015.)

## Regression check (SC-005)

```bash
cd backend && pytest -q
cd ../grading-agent && pytest -q
cd ../tutor-agent && pytest -q
cd ../frontend && npm test
```

**Expected**: all four suites pass with zero existing test file edited —
the only new files are the two content artifacts and whatever new
fixtures/tests this feature's own tasks add against them.

## Live Validation Results (2026-10-05, T015)

Run once against a real, freshly migrated (`alembic stamp base` +
`upgrade head`, the documented recovery for this sandbox's known
stamped-past-migrations flake -- hit again here, same as Milestones 11/24)
and seeded dev database, via a throwaway `TestClient`-based script (not
committed), matching Milestone 23's own precedent:

- Setup: both subjects loaded (`validated_at` set), `check_no_subject_
  conditionals.py` clean.
- Scenario 1: `algebra-2`/`physics` both show exactly 8 topics, zero
  incomplete (`skill_definition`/`career_connection`), zero missing a
  `standards_tags` row -- all three SQL checks returned the expected
  empty/8-row results.
- Scenario 2: placement-start + submit + mastery-state-read all `200`
  for both `algebra-2` (5 questions generated) and `physics`, each
  producing an 8-topic mastery-state response.
- Scenario 3 + FR-009: `POST /api/rosters` with `grade: 8` against
  `physics` returned `422` as expected; `grade: 9` returned `201`.
  Full assignment round trip (create -> guardian starts -> guardian
  answers -> instructor report) returned `201`/`201`/`200`/`200`, with
  the report showing `status: "completed"`, `score: {"correct": 1,
  "total": 1}` for the one targeted learner.
- Full regression (T014, run separately): `backend` 857/857,
  `grading-agent` 32/32, `tutor-agent` 41/41, `frontend` 221/221.

One sandbox-specific note: running the full `backend` pytest suite
against this same dev database drops and recreates its schema via
`tests/conftest.py`'s session-scoped fixture, so the live-loaded content
above did not survive that run -- re-seeded via the same Setup commands
immediately before this validation pass. Not a defect in this feature;
recorded so a future run in this sandbox isn't surprised by it.
