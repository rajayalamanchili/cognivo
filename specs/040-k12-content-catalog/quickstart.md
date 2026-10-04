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

```bash
curl -s "$BACKEND_URL/api/demo-learner"   # note learner_id
curl -s -X POST "$BACKEND_URL/api/placement/start" \
  -H "Content-Type: application/json" \
  -d '{"learner_id": "<demo_learner_id>", "subject_id": "algebra-2"}'
```

**Expected**: placement starts and returns a first question exactly as it
would for `subject_id: "algebra-1"` — same response shape, same
behavior. Answer a question through to a mastery-state update:

```bash
curl -s "$BACKEND_URL/api/learners/<demo_learner_id>/mastery-state?subject_id=algebra-2"
```

**Expected**: mastery state reflects the Sequencing Agent's standard BKT
update, identical in shape to an Algebra I/Biology mastery-state read.
Repeat both calls with `subject_id: "physics"` to confirm the same holds
for the second new subject.

## Scenario 3 — User Story 2: instructor can assign and review a new subject (SC-004)

As a seeded demo instructor with a roster:

```bash
curl -s -X POST "$BACKEND_URL/api/quiz-assignments" \
  -H "Content-Type: application/json" \
  -d '{"roster_id": "<roster_id>", "subject_id": "physics", "topic_ids": ["kinematics-motion-in-one-dimension"], "question_count": 5}'
```

**Expected**: assignment creation succeeds with `physics` selectable
exactly as `algebra-1`/`biology` already are — no new field, no new
error path. Have a guardian complete the assignment on a targeted
learner's behalf, then:

```bash
curl -s "$BACKEND_URL/api/quiz-assignments/<assignment_id>/report"
```

**Expected**: per-learner status/score renders identically to an
Algebra I/Biology assignment report.

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
