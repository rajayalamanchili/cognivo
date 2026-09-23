# Quickstart: Timed Practice and Quiz Mode

**Feature**: `022-timed-practice-quiz-mode` | **Date**: 2026-09-23

Validates the acceptance scenarios in `spec.md` end to end against a
real, migrated dev database. See `contracts/api.md` for full
request/response shapes and `data-model.md` for the schema this relies
on.

## Prerequisites

- `backend/` dependencies installed (`uv sync`), `DATABASE_URL` pointed
  at a migrated dev database (`uv run alembic upgrade head`).
- At least one seeded demo learner and a validated subject/topic set
  (same seed data every prior milestone's quickstart already relies
  on).
- Backend running locally (`uv run uvicorn src.main:app --reload`, or
  equivalent per this repo's existing dev workflow).

## Scenario 1: Timed quiz -- learner-completed before expiry (User Story 1)

1. `POST /api/quizzes` with `time_limit_seconds: 1800` and a short
   `question_count` (e.g. `2`).
2. Confirm the response includes a non-null `expires_at`.
3. Answer both questions via `POST /api/questions/{question_id}/answer`.
4. `GET /api/quizzes/{quiz_session_id}` -- expect `status: completed`,
   `end_reason: completed`, `elapsed_seconds` less than
   `time_limit_seconds`.

**Expected**: Score matches what an identical untimed quiz (omit
`time_limit_seconds` in step 1) would produce for the same answers --
directly validates FR-004/SC-003.

## Scenario 2: Timed quiz -- timer expires mid-attempt (User Story 1)

1. `POST /api/quizzes` with a very short `time_limit_seconds` (e.g.
   `1`, for test purposes) and `question_count: 5`.
2. Wait past expiry (sleep past 1 second).
3. Call `GET /api/quizzes/{quiz_session_id}/next-question`.

**Expected**: `409` response; `GET /api/quizzes/{quiz_session_id}`
shows `status: ended_early`, `end_reason: timer_expired` -- validates
FR-003/SC-002.

## Scenario 3: Timed practice session (User Story 2)

1. `POST /api/practice-sessions` with a `subject_id` and
   `time_limit_seconds: 1800`.
2. Confirm a `practice_session_id` and non-null `expires_at` are
   returned, and the first question's topic came from the Sequencing
   Agent (same topic-selection behavior as ordinary practice).
3. Answer a question via `POST /api/questions/{question_id}/answer`
   (the question's `practice_session_id` is set).
4. Confirm ordinary untimed practice
   (`GET /api/learners/{learner_id}/next-question`) is completely
   unaffected -- no `practice_session_id` on questions generated
   through that route, no new audit event -- validates FR-009.

## Scenario 4: Manual early-end (FR-010)

1. Start a timed quiz (Scenario 1, step 1) or timed practice session
   (Scenario 3, step 1).
2. `POST /api/quizzes/{quiz_session_id}/end` (or the practice-session
   equivalent) before answering every question or reaching expiry.

**Expected**: `200`, `status: ended_early`; the summary route shows
`end_reason: manually_ended_early`. Repeating the same call now returns
`409`.

## Scenario 5: Post-session summary (User Story 3)

For any session ended by Scenarios 1-4, `GET
/api/quizzes/{quiz_session_id}` (or the practice-session equivalent)
returns non-null `time_limit_seconds`, `elapsed_seconds`, and
`end_reason` -- validates SC-005. Repeat with an untimed quiz and
confirm all three fields are `null`.

## Regression check

Run the full backend suite (`uv run pytest`) and confirm every
Milestone 1-19 test still passes unmodified -- validates SC-004. Run
`uv run alembic check` (Milestone 19's own schema-drift gate) against
this feature's migration to confirm no model/migration drift before
opening a PR.
