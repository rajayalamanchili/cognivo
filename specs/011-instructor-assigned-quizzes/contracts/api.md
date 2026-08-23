# API Contract: Instructor-Assigned Quizzes

**Feature**: `011-instructor-assigned-quizzes` | **Date**: 2026-08-23

Extends `specs/010-instructor-classroom/contracts/api.md`'s
authenticated surface and `specs/005-adaptive-quiz/contracts/api.md`'s
quiz endpoints. New routes below require the session cookie noted;
`GET /api/quizzes/{quiz_session_id}/next-question` and
`POST /api/questions/{question_id}/answer` are **existing, unmodified
routes** (spec 005) whose contracts are unchanged except for one added
authorization branch (see "Extended existing routes" at the bottom).

## Assignments (instructor-facing)

### `POST /api/rosters/{roster_id}/assignments` (instructor-authenticated, owner only)

```json
{
  "topic_ids": ["topic-1", "topic-2"],
  "question_count": 5,
  "due_at": "2026-09-01T00:00:00Z",
  "learner_ids": ["<uuid>", "<uuid>"]
}
```
`learner_ids` MAY be the literal string `"all"` instead of a list, to
target every learner currently enrolled in the roster (FR-002).
`due_at` is optional (omit or `null` for no due date).

`201`:
```json
{
  "assignment_id": "...",
  "roster_id": "...",
  "subject_id": "...",
  "topic_ids": ["topic-1", "topic-2"],
  "question_count": 5,
  "due_at": "2026-09-01T00:00:00Z",
  "target_learner_ids": ["<uuid>", "<uuid>"]
}
```

`403 not_roster_owner` if the instructor does not own `roster_id`
(FR-004). `422 empty_target` if the resolved target list is empty
(FR-003 -- either an explicit empty `learner_ids` list, or `"all"`
against a roster with zero enrollments). `404` if any `topic_id` is
unknown or spans a subject other than the roster's own (mirrors
`quiz.py`'s existing `_resolve_quiz_subject_id` validation, research.md
data-model.md).

### `GET /api/rosters/{roster_id}/assignments` (instructor-authenticated, owner only)

`200`:
```json
{
  "assignments": [
    { "assignment_id": "...", "topic_ids": [...], "question_count": 5,
      "due_at": "...", "cancelled_at": null, "created_at": "..." }
  ]
}
```

### `GET /api/rosters/{roster_id}/assignments/{assignment_id}` (instructor-authenticated, owner only)

`200`:
```json
{
  "assignment_id": "...",
  "topic_ids": [...],
  "question_count": 5,
  "due_at": "...",
  "cancelled_at": null,
  "learners": [
    { "learner_id": "...", "display_name": "Jamie", "status": "completed",
      "score": { "correct": 4, "total": 5 } },
    { "learner_id": "...", "display_name": "Alex", "status": "not_started",
      "score": null }
  ]
}
```
`status` is one of `not_started` / `in_progress` / `completed` /
`ended_early` (data-model.md's derived-status table, FR-010). `score`
is `null` unless `status` is `completed` or `ended_early`.

### `DELETE /api/rosters/{roster_id}/assignments/{assignment_id}` (instructor-authenticated, owner only)

No body. `204`. Sets `cancelled_at`; does not delete the assignment,
its target rows, or touch any learner's recorded mastery-state updates
(FR-012, research.md §6). `409 already_cancelled` if called twice.

## Assignments (guardian-facing)

### `GET /api/learners/{learner_id}/assignments` (guardian-authenticated, own learner only)

`200`:
```json
{
  "assignments": [
    { "assignment_id": "...", "topic_ids": [...], "question_count": 5,
      "due_at": "...", "status": "not_started" }
  ]
}
```
Lists every non-cancelled assignment targeting this learner, with the
same derived `status` as the instructor view. `403 not_your_learner` if
the requesting guardian does not own `learner_id` (mirrors
`learners.py`'s existing ownership check).

### `POST /api/assignments/{assignment_id}/learners/{learner_id}/start` (guardian-authenticated, own learner only)

No body. `201`:
```json
{
  "quiz_session_id": "...",
  "status": "in_progress",
  "question": { "question_id": "...", "topic_id": "...", "difficulty": "...",
                "question_type": "...", "stem": "...", "options": [...] }
}
```
Identical response shape to `POST /api/quizzes` (spec 005) -- internally
calls the same `start_quiz()` / `generate_quiz_question()` functions
(research.md §1/§2). Sets `quiz_assignment_targets.quiz_session_id` in
the same transaction.

Failure modes: `403 not_your_learner` (guardian doesn't own the
learner); `403 not_targeted` (learner isn't in this assignment's target
list); `409 already_attempted` (`quiz_session_id` already set --
FR-014); `409 past_due` (`due_at` has passed -- FR-014); `409
assignment_cancelled` (FR-011/research.md §6); `403 not_enrolled` (the
learner was unenrolled from the roster after being targeted -- FR-011).

## Extended existing routes

### `GET /api/quizzes/{quiz_session_id}/next-question` and `POST /api/questions/{question_id}/answer`

Behavior for a `QuizSession` **not** linked to any
`quiz_assignment_targets` row is completely unchanged from spec 005.

For a `QuizSession` that **is** assignment-linked, both routes now also
require a guardian session cookie matching that target's learner's
`guardian_id` (research.md §2); absence or mismatch returns `403
not_learner_guardian`. No other part of either route's contract
changes -- same request/response shapes as spec 005.
