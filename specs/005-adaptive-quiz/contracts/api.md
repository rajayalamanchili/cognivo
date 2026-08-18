# API Contract: Adaptive Difficulty Quiz

**Feature**: `005-adaptive-quiz` | **Date**: 2026-08-18

Extends `specs/001-domain-agnostic-core/contracts/api.md`'s FastAPI
backend -- same Vercel Python Function, same stateless-per-request
model. All request/response bodies are JSON. Learner is resolved
server-side via `get_demo_learner` (same as placement), never a path
param, since Milestone 1-5 has exactly one seeded learner.

## `POST /api/quizzes` (NEW)

Starts a quiz and generates its first question.

**Request**:
```json
{ "topic_ids": ["linear-equations"], "question_count": 5 }
```

**Response** `200` (quiz starts normally):
```json
{
  "quiz_session_id": "uuid",
  "status": "in_progress",
  "question": {
    "question_id": "uuid",
    "topic_id": "linear-equations",
    "difficulty": "easy",
    "question_type": "multiple_choice",
    "stem": "...",
    "options": ["a", "b", "c", "d"]
  }
}
```

**Response** `200` (dedup retries exhausted on the very first
question -- research.md §3):
```json
{ "quiz_session_id": "uuid", "status": "ended_early", "question": null }
```

**Field notes**: The first question is always requested at `easy`
difficulty per topic (same "unknown -> easy" convention as placement
and Milestone 1's next-question), for `topic_ids[0]` (round-robin
starts at the first selected topic).

**Errors**: `422` if `topic_ids` is empty, contains a duplicate, or
`question_count` is outside `1`-`50` inclusive (spec.md FR-001). `404`
if any `topic_id` is unknown or belongs to an unvalidated subject, or
if `topic_ids` spans more than one subject (a quiz is single-subject,
matching every other topic-scoped endpoint's `subject_id` gate).

**Side effects**: Creates one `QuizSession` row (`status=in_progress`)
and one `GeneratedQuestion` row (`quiz_session_id` set). Wrapped in
`traced_request()` (calls the Assessment-Generation Agent, same as
placement/next-question).

---

## `GET /api/quizzes/{quiz_session_id}/next-question` (NEW)

Returns the next question in the quiz's round-robin + streak-based
difficulty rule (research.md §1-§2). Only valid while the quiz is
`in_progress`.

**Path params**: `quiz_session_id` (UUID)

**Response** `200` (next question generated normally):
```json
{
  "status": "in_progress",
  "question": {
    "question_id": "uuid",
    "topic_id": "linear-equations",
    "difficulty": "medium",
    "question_type": "numeric",
    "stem": "...",
    "options": null
  }
}
```

**Response** `200` (dedup retries exhausted for this topic --
research.md §3):
```json
{ "status": "ended_early", "question": null }
```

**Errors**: `404` if `quiz_session_id` is unknown. `409` if the quiz's
`status` is already `completed` or `ended_early` -- the client should
call `GET /api/quizzes/{quiz_session_id}` for the summary instead of
retrying this endpoint.

**Side effects**: Same as `POST /api/quizzes` per question generated:
one new `GeneratedQuestion` row, `quiz_session_id` set; on
`ended_early`, no new row, `QuizSession.status` updated instead. Wrapped
in `traced_request()`.

---

## `POST /api/questions/{question_id}/answer` (UNCHANGED contract, extended internally)

Same request/response shape as `specs/001-domain-agnostic-core/contracts/api.md`
-- no new field, no behavior change visible in the response body. If
the answered question's `quiz_session_id` is set (research.md §4), this
call additionally:
- Logs one `quiz_difficulty_adjusted` `AssessmentEvent` (FR-009,
  data-model.md).
- Marks `QuizSession.status = "completed"` (with `completed_at` set) if
  this quiz's answered-question count has now reached its
  `question_count`.

A client cannot distinguish a quiz answer from a non-quiz answer by
this response alone -- it must separately call
`GET /api/quizzes/{quiz_session_id}/next-question` (which will `409`
once the quiz is complete) or poll `GET /api/quizzes/{quiz_session_id}`
to learn the quiz's current status.

---

## `GET /api/quizzes/{quiz_session_id}` (NEW)

Reads a quiz's current status, and its score/summary once it has
reached `completed` or `ended_early`.

**Path params**: `quiz_session_id` (UUID)

**Response** `200`:
```json
{
  "quiz_session_id": "uuid",
  "subject_id": "algebra-1",
  "topic_ids": ["linear-equations"],
  "question_count": 5,
  "status": "completed",
  "started_at": "2026-08-18T12:00:00Z",
  "completed_at": "2026-08-18T12:03:00Z",
  "score": { "correct": 4, "total": 5 },
  "summary": [
    { "topic_id": "linear-equations", "difficulty": "easy", "correct": 1, "total": 1 },
    { "topic_id": "linear-equations", "difficulty": "medium", "correct": 2, "total": 3 },
    { "topic_id": "linear-equations", "difficulty": "hard", "correct": 1, "total": 1 }
  ]
}
```

**Field notes**: `score`/`summary` reflect only questions answered so
far -- while `status = "in_progress"`, this is a partial, in-progress
tally (not an error), matching FR-006's "already-answered questions are
never lost" even before completion. `summary` groups by
(`topic_id`, `difficulty`) in the order those combinations were first
encountered.

**Errors**: `404` if `quiz_session_id` is unknown.

**Side effects**: None -- pure read, not wrapped in `traced_request()`
(no LLM/ADK call), matching the existing `GET /mastery-state` precedent.
