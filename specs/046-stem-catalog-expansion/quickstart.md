# Quickstart: STEM Catalog Expansion (Remaining Six Subjects)

**Feature**: `046-stem-catalog-expansion` | **Date**: 2026-10-12

Validates all three user stories against a real dev database. No
migration ships with this feature -- `alembic upgrade head` should be a
no-op; only new content-artifact *rows* are written via the existing
loader script. Reuses the seeded demo learner and the existing
placement/practice/quiz-assignment/instructor-dashboard flows.

## Setup

```bash
cd backend
# confirm no pending migration (this feature adds none)
alembic current  # should already equal alembic heads

for subject in pre-algebra geometry chemistry earth-science elementary-math elementary-science; do
  python scripts/load_content_artifact.py "content/$subject/subject.yaml"
done
python scripts/check_no_subject_conditionals.py   # must stay clean (FR-007)
```

**Expected**: all six loads exit `0`; `check_no_subject_conditionals.py`
reports no violations -- confirming zero engine code branches on any of
the six new `subject_id`s or any new conditional at all.

## Scenario 1 -- User Story 3: new subjects pass the existing content gate (SC-002)

```sql
SELECT subject_id, COUNT(*) AS topic_count
FROM topics
WHERE subject_id IN ('pre-algebra', 'geometry', 'chemistry', 'earth-science', 'elementary-math', 'elementary-science')
GROUP BY subject_id;
-- expect: 8 for each of the six subject_ids

SELECT subject_id, topic_id FROM topics
WHERE subject_id IN ('pre-algebra', 'geometry', 'chemistry', 'earth-science', 'elementary-math', 'elementary-science')
  AND (skill_definition IS NULL OR career_connection IS NULL);
-- expect: zero rows (every topic has both)

SELECT t.subject_id, t.topic_id FROM topics t
LEFT JOIN (
  SELECT subject_id, topic_id, COUNT(*) AS n FROM standards_tags
  GROUP BY subject_id, topic_id
) s ON s.subject_id = t.subject_id AND s.topic_id = t.topic_id
WHERE t.subject_id IN ('pre-algebra', 'geometry', 'chemistry', 'earth-science', 'elementary-math', 'elementary-science')
  AND (s.n IS NULL OR s.n = 0);
-- expect: zero rows (every topic carries at least one real standards tag)
```

Then confirm rejection still works, without touching any file
permanently: temporarily edit one topic in a scratch copy of
`content/geometry/subject.yaml` to add a `prerequisites` entry naming a
topic that doesn't exist in that subject, and re-run the loader against
the scratch copy.

**Expected**: load fails with the same "unknown prerequisite" error
class every existing subject already produces -- no new error type,
confirming research.md Decision 2 (prerequisites remain
same-subject-only).

## Scenario 2 -- User Story 1: learner can select and work through a new subject, including elementary grades (SC-001, SC-003)

Placement always resolves to the single seeded demo learner
(`services/demo_learner.get_demo_learner`, Milestone 1):

```bash
curl -s -X POST "$BACKEND_URL/api/subjects/geometry/placement/start"
```

**Expected**: placement starts and returns a first question exactly as
it would for `subject_id: "algebra-1"` -- same response shape, same
behavior. Answer each question via
`POST /api/placement/{placement_session_id}/submit`, then read mastery
state:

```bash
curl -s "$BACKEND_URL/api/learners/<demo_learner_id>/mastery-state?subject_id=geometry"
```

**Expected**: mastery state reflects the Sequencing Agent's standard
BKT update, identical in shape to an existing subject's mastery-state
read. Repeat both calls for `pre-algebra`, `chemistry`, `earth-science`,
`elementary-math`, and `elementary-science` to confirm the same holds
for every new subject.

For the two elementary subjects specifically, also confirm
`unlocked_grade` reflects grades 1-5 for the first time in this
catalog:

```bash
curl -s "$BACKEND_URL/api/learners/<demo_learner_id>/mastery-state?subject_id=elementary-math"
```

**Expected**: the response's `unlocked_grade` field (`MasteryStateResponse`,
`src/api/routes/mastery.py`) resolves to a value in `1`-`5` -- no error,
no fallback to `None`/ungraded behavior. Feeding that value into
`determine_mediation_tier` (`services/mediation/tier.py`) yields
`CO_PRESENT` (grades 1-2) or `CHECK_IN` (grades 3-5), the same tiers
already exercised by older-grade subjects today, confirming
research.md Decision 6.

## Scenario 3 -- User Story 2: instructor can assign and review a new subject, including FR-009 grade validation (SC-004)

As an authenticated instructor with a roster already created for
`chemistry` (`POST /api/rosters`, optionally declaring `grade`):

```bash
curl -s -X POST "$BACKEND_URL/api/rosters/<roster_id>/assignments" \
  -H "Content-Type: application/json" \
  -d '{"topic_ids": ["atomic-structure"], "question_count": 1, "learner_ids": "all"}'
```

**Expected**: assignment creation succeeds with `chemistry` selectable
exactly as any existing subject already is -- no new field, no new
error path. Have a guardian complete the assignment on a targeted
learner's behalf, then:

```bash
curl -s "$BACKEND_URL/api/rosters/<roster_id>/assignments/<assignment_id>"
```

**Expected**: per-learner status/score renders identically to an
existing-subject assignment report. Separately (FR-009, reusing
Milestone 040's existing check): `POST /api/rosters` with
`{"subject_id": "chemistry", "grade": 11}` is rejected `422`
(`chemistry` declares `grade_bands: [9, 10]`); the same call with
`grade: 9` succeeds. Repeat once against `elementary-math` with
`grade: 6` (rejected, outside `[1-5]`) and `grade: 3` (succeeds) to
confirm FR-009 applies identically at the low end of the grade range.

## Regression check (SC-005)

```bash
cd backend && pytest -q
cd ../grading-agent && pytest -q
cd ../tutor-agent && pytest -q
cd ../frontend && npm test
```

**Expected**: all suites pass with zero existing test file edited -- the
only new files are the six content artifacts and whatever new
fixtures/tests this feature's own tasks add against them.
