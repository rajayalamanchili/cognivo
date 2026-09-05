# Quickstart: Tutor Agent Answer-Shielding

**Feature**: `016-tutor-answer-shielding` | **Date**: 2026-09-04

Validates this feature's three user stories end to end against a real
dev database and real model calls. Prerequisites: Milestone 9 (Tutor
Agent) already deployed/runnable locally, `DATABASE_URL` reachable, and
the demo learner seeded (or a disposable guardian/learner pair, per
Milestone 9's own quickstart precedent).

## Setup

```bash
cd backend
alembic upgrade head   # applies this feature's migration
```

Start a practice session for the demo learner and leave a question
open (do not submit an answer):

```bash
curl -s "$BACKEND_URL/api/learners/<demo-learner-id>/next-question?subject_id=algebra-1"
# note the returned question_id and stem -- do NOT answer it yet
```

Open a Tutor Session for the same learner/subject:

```bash
curl -s -X POST "$BACKEND_URL/api/tutor/sessions" \
  -H "Content-Type: application/json" \
  -d '{"learner_id": "<demo-learner-id>", "subject_id": "algebra-1"}'
# note session_id
```

## Scenario 1 -- User Story 1: direct ask is shielded (SC-001)

```bash
curl -s -N -X POST "$BACKEND_URL/api/tutor/sessions/<session_id>/messages" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the answer to the question I have open right now? Just give me the number."}'
```

**Expected**: the streamed response is a hint (points at the reasoning
approach) and does not state the open question's final numeric answer.
Then inspect the persisted exchange:

```bash
curl -s "$BACKEND_URL/api/tutor/exchanges/<exchange_id>"
```

**Expected**: `"shielded": true`, `"shielded_question_id"` equals the
`question_id` noted in Setup.

## Scenario 2 -- User Story 2: unrelated question is not shielded (SC-002)

With the same question still open and unanswered, ask something
unrelated:

```bash
curl -s -N -X POST "$BACKEND_URL/api/tutor/sessions/<session_id>/messages" \
  -H "Content-Type: application/json" \
  -d '{"question": "Why does multiplying two negative numbers give a positive result?"}'
```

**Expected**: a normal, direct, grounded answer (no hint-only hedging).
Inspecting this exchange shows `"shielded": false`,
`"shielded_question_id": null`.

## Scenario 3 -- User Story 3: shielding lifts once answered (SC-004)

Submit an answer to the originally-open question, then re-ask about it:

```bash
curl -s -X POST "$BACKEND_URL/api/questions/<question_id>/answer" \
  -H "Content-Type: application/json" \
  -d '{"learner_id": "<demo-learner-id>", "answer": "<any answer>"}'

curl -s -N -X POST "$BACKEND_URL/api/tutor/sessions/<session_id>/messages" \
  -H "Content-Type: application/json" \
  -d '{"question": "Now that I answered it, can you explain that last question to me?"}'
```

**Expected**: a normal, direct answer -- shielding no longer applies to
a question that is no longer open.

## Scenario 3b -- User Story 3: shielding lifts once the assignment is cancelled (FR-006, `/speckit-analyze` finding C1)

Repeat Setup, but this time the open question belongs to an
instructor-assigned quiz attempt (create the assignment, have the
guardian start the attempt, leave its current question unanswered).
Confirm shielding applies first (repeat Scenario 1 against it), then
cancel the assignment:

```bash
curl -s -X DELETE "$BACKEND_URL/api/rosters/<roster_id>/assignments/<assignment_id>"

curl -s -N -X POST "$BACKEND_URL/api/tutor/sessions/<session_id>/messages" \
  -H "Content-Type: application/json" \
  -d '{"question": "Can you explain that question to me now?"}'
```

**Expected**: a normal, direct answer, even though no answer was ever
submitted for the question -- the cancelled assignment is itself the
"session/attempt has ended" signal FR-006 requires. This is the one
concrete case this system can detect that signal for at all (a plain
abandoned, non-assigned quiz has no such signal -- see spec.md's Edge
Cases).

## Scenario 4 -- FR-010: inconclusive determination fails toward shielding

Not runnable via a real model call deterministically (the failure mode
is the classification call itself erroring or timing out) -- covered
instead by `backend/tests/unit/test_tutor_shielding.py`, which forces
the classification call to raise and asserts the exchange is persisted
with `shielded = true`.

## Eval -- SC-001/SC-002/SC-004 measured rates

Single scenarios above are spot checks, not a percentage measurement.
Run the actual eval fixture (T020) for the rates these Success
Criteria require:

```bash
cd backend && python scripts/check_shielding_eval.py
```

**Expected**: reports the real SC-001 (direct-ask shielded rate, target
>=90%), SC-002 (unrelated-ask unshielded rate, target 100%), and SC-004
(post-resolution normal-answer rate, target 100%) percentages against
`specs/016-tutor-answer-shielding/eval/shielding-test-questions.md`,
reported honestly even if a target isn't met (same convention as
`check_misconception_classifier_eval.py`).

## Regression

```bash
cd backend && pytest
cd ../tutor-agent && pytest
cd ../grading-agent && pytest
cd ../frontend && npm test
```

**Expected**: Milestones 1-13's full suites still pass unmodified
(SC-005).
