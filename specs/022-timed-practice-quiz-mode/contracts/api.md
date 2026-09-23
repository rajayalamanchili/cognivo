# API Contract: Timed Practice and Quiz Mode

**Feature**: `022-timed-practice-quiz-mode` | **Date**: 2026-09-23

Extends `specs/005-adaptive-quiz/contracts/api.md`'s quiz routes and
adds a new, parallel set of routes for timed practice (ordinary
practice's existing `GET /api/learners/{learner_id}/next-question` is
untouched -- FR-009, no timer path through it at all). All new/changed
fields are optional on the request side and additive on the response
side, so every existing untimed caller sees identical behavior.

## `POST /api/quizzes` (EXTENDED)

**Request** gains one new optional field:
```json
{ "topic_ids": ["linear-equations"], "question_count": 5, "time_limit_seconds": 1800 }
```
`time_limit_seconds` omitted or `null` -- unchanged, untimed behavior
(FR-001/FR-009). When present, MUST be a positive integer from the
preset list the frontend offers (spec.md Assumptions: e.g.
900/1800/2700/3600 for 15/30/45/60 minutes); `422` otherwise.

**Response** gains one new field, always present:
```json
{
  "quiz_session_id": "uuid",
  "status": "in_progress",
  "question": { "...": "..." },
  "expires_at": "2026-09-23T14:30:00Z"
}
```
`expires_at` is `null` when untimed, otherwise
`started_at + time_limit_seconds` (research.md §1) -- the frontend
countdown (FR-002) is built from this timestamp, never from a
client-side duration guess.

**Side effects**: `QuizSession.time_limit_seconds` set from the
request. No other change to `POST /api/quizzes`' existing side effects.

---

## `GET /api/quizzes/{quiz_session_id}/next-question` (EXTENDED)

**New behavior**: Before generating a question, checks whether the quiz
is timed and past `expires_at` (research.md §1). If so: transitions
`QuizSession.status` to `ended_early`, writes one `timed_session_ended`
event (`end_reason=timer_expired`, data-model.md), and returns `409`
(same status code family the untimed path already uses for
"already completed/ended_early") instead of generating a question.

**Response**, unchanged shape otherwise, `expires_at` echoed identically
to the `POST /api/quizzes` response.

---

## `POST /api/questions/{question_id}/answer` (EXTENDED internally, no new field)

**New behavior**: If the answered question's `quiz_session_id` (or, for
the new practice flow, `practice_session_id`) points at a timed session
already past `expires_at`, the answer is rejected with `409` before
scoring -- the same lazy-expiry check as the `next-question` route,
applied here too since an answer can arrive after expiry even without
an intervening `next-question` call. Scoring for an answer accepted
before expiry is computed identically to an untimed answer (FR-004) --
no new field in the response body.

**New behavior (FR-011, applies to every call, timed or not)**: The
`answer_submitted` audit event this route already writes gains one new
`time_spent_seconds` payload key (data-model.md), computed from
`GeneratedQuestion.shown_at` to now. Not visible in this route's
response body -- it is audit-log-only, read back via the same event
query any existing dashboard already uses.

---

## `POST /api/quizzes/{quiz_session_id}/end` (NEW)

Manually ends an `in_progress` timed quiz before its time limit or
question count is reached (FR-010, research.md §4). `404` if
`untimed` (`time_limit_seconds IS NULL`) -- there is nothing to
manually end early on an untimed quiz, since the learner can simply
stop calling `next-question`. `409` if already `completed`/
`ended_early`.

**Response** `200`:
```json
{ "quiz_session_id": "uuid", "status": "ended_early" }
```

**Side effects**: `QuizSession.status = ended_early`,
`completed_at` set, one `timed_session_ended` event written
(`end_reason=manually_ended_early`).

---

## `GET /api/quizzes/{quiz_session_id}` (EXTENDED)

**Response** gains fields present only when the quiz was timed:
```json
{
  "status": "ended_early",
  "started_at": "...",
  "completed_at": "...",
  "score": { "...": "..." },
  "summary": [ "..." ],
  "time_limit_seconds": 1800,
  "elapsed_seconds": 1742,
  "end_reason": "timer_expired"
}
```
All three new fields are `null` for an untimed quiz (User Story 3,
SC-005).

---

## `POST /api/practice-sessions` (NEW)

Starts a timed practice session and generates its first question.
Ordinary untimed practice keeps using
`GET /api/learners/{learner_id}/next-question` directly, unchanged --
this route exists only for the timed path (FR-008).

**Request**:
```json
{ "learner_id": "uuid", "subject_id": "algebra-1", "time_limit_seconds": 1800 }
```
`time_limit_seconds` is required here (unlike the quiz route) --
`practice_sessions` only exists for timed practice (data-model.md).

**Response** `200`:
```json
{
  "practice_session_id": "uuid",
  "status": "in_progress",
  "expires_at": "2026-09-23T14:30:00Z",
  "question": { "...": "..." }
}
```

**Errors**: `404` if `subject_id` is unknown or unvalidated (same gate
`GET /next-question` already applies). `422` if `time_limit_seconds`
is missing or outside the same preset list `POST /api/quizzes` accepts.

**Side effects**: Creates one `PracticeSession` row and one
`GeneratedQuestion` row (`practice_session_id` set, topic chosen by the
Sequencing Agent exactly as ordinary practice already does). Wrapped in
`traced_request()`, same as every other question-generating route.

---

## `GET /api/practice-sessions/{practice_session_id}/next-question` (NEW)

Same lazy-expiry-check shape as the quiz route above. `409` if the
session is already `completed`/`ended_early`, or if this call is what
discovers the session is past `expires_at` (transitions it to
`ended_early` first, same as the quiz path).

---

## `POST /api/practice-sessions/{practice_session_id}/end` (NEW)

Same shape as `POST /api/quizzes/{quiz_session_id}/end` -- manual
early-end, `409` if already terminal. No "untimed" `404` case here
(every `practice_sessions` row is timed by construction).

---

## `GET /api/practice-sessions/{practice_session_id}` (NEW)

Summary route, same shape as the extended `GET /api/quizzes/{...}`
above minus `score`/`summary`'s quiz-specific breakdown-by-topic shape
-- practice has no `question_count` to score "out of," so this returns
a simple correct/total count derived the same way
(`compute_quiz_summary`'s existing logic, generalized to accept either
session id column) plus `time_limit_seconds`/`elapsed_seconds`/
`end_reason`, always present since every practice session is timed.
