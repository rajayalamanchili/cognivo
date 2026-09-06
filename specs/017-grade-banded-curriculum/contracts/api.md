# API Contract: Grade-Banded Curriculum Scoping

**Feature**: `017-grade-banded-curriculum` | **Date**: 2026-09-06

One new endpoint. Two existing endpoints gain response fields but keep
their existing request shapes, status codes, and auth (none, Milestone
1's solo-demo-learner model, unchanged). `submit_placement`'s request
and response shapes are entirely unchanged (`research.md` Decision 6).

## `POST /api/subjects/{subject_id}/placement/start` (EXISTING, response fields ADDED)

Selection logic changes internally (grade-entry topics instead of
subject-wide entry-level topics, for a graded subject -- `research.md`
Decision 2); the endpoint's path, method, and request body (none) are
unchanged.

Response (`PlacementStartResponse`), each question gains `grade`:

```json
{
  "placement_session_id": "...",
  "questions": [
    {
      "question_id": "...",
      "topic_id": "solving-one-step-equations",
      "grade": 6,
      "difficulty": "easy",
      "question_type": "numeric",
      "stem": "...",
      "options": null
    }
  ]
}
```

- `grade` (`int | null`): `null` for an ungraded subject's questions
  (unchanged Milestone 1 behavior); an `int` for a graded subject,
  always present on every question in that response (FR-002 -- every
  placement question shown MUST be labeled with its grade).

## `POST /api/placement/{placement_session_id}/skip` (NEW)

Request:

```json
{ "question_id": "..." }
```

Response (`200`):

```json
{
  "replacement_question": {
    "question_id": "...",
    "topic_id": "integers-and-operations",
    "grade": 4,
    "difficulty": "easy",
    "question_type": "multiple_choice",
    "stem": "...",
    "options": ["...", "...", "...", "..."]
  }
}
```

`replacement_question` is `null` when no eligible lower-or-equal-grade,
not-yet-shown-in-this-session topic remains (FR-008's bounded-
termination case) -- the client proceeds to `submit_placement` with
whatever question set it already has; this is not an error response.

**Errors**:
- `404` -- `question_id` does not exist, or does not belong to
  `placement_session_id`.
- `409` -- `question_id` has already been answered (reuses the existing
  `_already_answered` check `submit_placement` already applies).
- `422` -- `question_id`'s grade is not strictly above the learner's
  interim currently-assessed level for this session (`research.md`
  Decision 4) -- i.e. this question was never eligible to skip in the
  first place (Acceptance Scenario 1 of User Story 3's precondition).
- `422` -- the subject has no `GradeBand` rows (skip is only meaningful
  for a graded subject's placement; an ungraded subject's placement
  flow is entirely unchanged and has nothing to skip *to*).

No `answer_key` or any other sensitive field is ever included in this
endpoint's response -- same field set as `start_placement`'s existing
`PlacementQuestionOut`.

## `POST /api/placement/{placement_session_id}/submit` (EXISTING, UNCHANGED)

Request and response shapes are identical to today. A skipped
question's `question_id` is simply never present in the submitted
`answers` array -- `submit_placement`'s existing "any topic with no
submitted answer reports `status: "unknown"`" behavior already
satisfies FR-007 with no code change (`research.md` Decision 6). This
endpoint additionally performs the one-time `GRADE_ASSIGNED` audit-log
write and creates the subject's `GradeProgress` row internally,
for a graded subject -- neither is visible in the response shape, only
in the audit log (`GET`-able the same way every other
`AssessmentEvent` already is).

## `GET /api/learners/{learner_id}/next-question` (EXISTING, no shape change)

Internal eligibility filtering changes (FR-005, `research.md` Decision
7's `unlocked_grade` gate in `rank_eligible_topics`); the endpoint's
request/response shape is unchanged. A learner who has not unlocked a
grade simply never sees that grade's topics selected -- no new field
communicates this to the caller, since nothing in spec.md asks for it
to be surfaced there (it is fully reconstructable from the audit log,
per FR-010).
