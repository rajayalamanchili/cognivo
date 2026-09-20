# Quickstart: Age-Adaptive Learner Experience

**Feature**: `019-age-adaptive-learner-experience` | **Date**: 2026-09-20

Validates all three user stories against a real dev database.
Prerequisites: Milestones 7, 8, and 15 already deployed/runnable
locally (`DATABASE_URL` reachable, guardian auth working, at least one
`QuizAssignment` flow available), `algebra-1`'s content artifact
already grade-banded (Milestone 15), `biology` left ungraded (doubles
as the SC-008 regression fixture, same precedent Milestones 15/16 used).

## Setup

```bash
cd backend
alembic upgrade head    # applies this feature's guardian_viewed_at migration
```

Seed two real guardian+learner pairs (one per grade extreme) via the
existing guardian sign-up/add-learner flow (Milestone 7), then use
Milestone 15's placement flow to place one learner's `algebra-1`
`unlocked_grade` at 2 (co-present) and the other's at 10 (independent).
A third and fourth pair at grades 4 (check-in) and 7 (opt-in-nudges) are
needed for SC-004/SC-005 specifically.

## Scenario 1 -- User Story 1: read-aloud offered only below grade 3 (SC-001, SC-002)

```bash
open "$FRONTEND_URL/practice?learner_id=<grade-1-learner-id>"
```

**Expected**: the question card shows a read-aloud control; clicking it
plays the question text and every answer choice aloud via the browser's
own text-to-speech; replaying does not navigate away or clear the
in-progress response (FR-002). Repeat against `/quiz` and `/placement`
for the same learner -- the control appears in all three flows (Decision
1: one shared `QuestionCard` component).

```bash
open "$FRONTEND_URL/practice?learner_id=<grade-10-learner-id>"
```

**Expected**: no read-aloud control appears (FR-003).

## Scenario 2 -- User Story 2: guardian starts every tier; hand-off token differs (SC-003)

```bash
curl -s -X POST "$BACKEND_URL/api/assignments/<assignment-id>/learners/<grade-2-learner-id>/start" \
  -b guardian_cookies.txt
```

**Expected** (co-present, grade 2): `handoff_token: null` in the
response. Then, from a session with no guardian cookie:

```bash
curl -s "$BACKEND_URL/api/quizzes/<quiz_session_id>/next-question"
```

**Expected**: `403 not_learner_guardian` -- no credential lets this
request through without the guardian's own session.

```bash
curl -s -X POST "$BACKEND_URL/api/assignments/<assignment-id>/learners/<grade-10-learner-id>/start" \
  -b guardian_cookies.txt
```

**Expected** (independent, grade 10): `handoff_token` is a non-null JWT.
Then, from a session with **no** guardian cookie:

```bash
curl -s "$BACKEND_URL/api/quizzes/<quiz_session_id>/next-question" \
  -H "X-Quiz-Handoff-Token: <handoff_token>"
```

**Expected**: `200`, the next question -- the learner's device
continues the quiz without the guardian's session present (FR-005b).

```bash
# after the quiz session completes:
curl -s "$BACKEND_URL/api/quizzes/<quiz_session_id>/next-question" \
  -H "X-Quiz-Handoff-Token: <same handoff_token>"
```

**Expected**: `409 quiz_session_not_in_progress` (FR-005c) -- the token
stops working once its quiz session is no longer in progress.

## Scenario 3 -- User Story 2: check-in summary vs. opt-in-nudges indicator, independent gets neither (SC-004, SC-005)

Complete a quiz session for the grade-4 (check-in), grade-7
(opt-in-nudges), and grade-10 (independent) learners from a device
using only their handoff tokens (as in Scenario 2), then, as each
learner's guardian:

```bash
curl -s "$BACKEND_URL/api/learners/<grade-4-learner-id>/assignments" -b guardian_cookies.txt
curl -s "$BACKEND_URL/api/learners/<grade-7-learner-id>/assignments" -b guardian_cookies.txt
curl -s "$BACKEND_URL/api/learners/<grade-10-learner-id>/assignments" -b guardian_cookies.txt
```

**Expected**: all three list entries show `status: "completed"`, but
only the grade-7 (opt-in-nudges) entry shows `has_unviewed_activity:
true` -- the grade-4 (check-in) and grade-10 (independent) entries show
`has_unviewed_activity: false` even though neither has been viewed yet
(FR-006/FR-008: the indicator is exclusive to opt-in-nudges). Load the
grade-4 learner's summary:

```bash
curl -s "$BACKEND_URL/api/quizzes/<quiz_session_id>" -b guardian_cookies.txt
```

**Expected**: a full score/summary payload (check-in tier, FR-006).
Now load the grade-7 learner's summary the same way, then re-fetch its
assignments list:

**Expected**: `has_unviewed_activity: false` for that entry now --
viewing the summary clears the flag (FR-007a's shared seam: the write
to `guardian_viewed_at` is the same for every tier; only the badge's
exposure is opt-in-nudges-only).

## Scenario 4 -- User Story 3: pacing checkpoint differs by grade band (SC-009)

```bash
open "$FRONTEND_URL/quiz?learner_id=<grade-1-learner-id>"
```

**Expected**: after `pacing.ts`'s configured question count for the
earliest band, a positive-reinforcement stopping point appears instead
of the next question loading immediately -- the learner can still
choose to continue (soft checkpoint, FR-009/Story 3 Acceptance Scenario
1); the quiz itself does not end on its own.

```bash
open "$FRONTEND_URL/quiz?learner_id=<grade-10-learner-id>"
```

**Expected**: no stopping point appears; questions continue loading
until the learner ends the quiz or it completes, exactly as today.

## Scenario 5 -- Regression: `biology` (ungraded) and demo learner are untouched (SC-008)

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/next-question?subject_id=biology"
```

**Expected**: byte-identical response shape to pre-feature behavior --
no read-aloud field, no tier/handoff concept surfaced anywhere in this
response (demo learner's quiz sessions are never assignment-linked,
Decision 3/`research.md` §3 -- this path is untouched by construction).

Run the full backend + frontend regression suites and confirm
Milestone 15's existing grade-banding tests still pass unmodified
(SC-006).
