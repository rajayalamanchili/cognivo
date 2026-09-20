# API Contract: Age-Adaptive Learner Experience

**Feature**: `019-age-adaptive-learner-experience` | **Date**: 2026-09-20

Extends `specs/011-instructor-assigned-quizzes/contracts/api.md`, which
itself extends `specs/005-adaptive-quiz/contracts/api.md`'s spec-005
routes. This feature adds no new routes -- read-aloud and pacing are
frontend-only (`research.md` §1/§6). It extends two existing routes'
response/request shapes and further extends spec 011's already-extended
guardian-authorization check.

## `POST /api/assignments/{assignment_id}/learners/{learner_id}/start` (EXTENDED)

Request/failure-mode contract unchanged from spec 011. Response gains
one new, nullable field:

```json
{
  "quiz_session_id": "...",
  "status": "in_progress",
  "question": { "...": "..." },
  "handoff_token": "eyJhbGciOi..." 
}
```

`handoff_token` is present (a signed JWT, `research.md` §4) whenever the
target learner's guardian-mediation tier (derived from their
`GradeProgress.unlocked_grade` for this assignment's subject,
`research.md` §3) is `check_in`, `opt_in_nudges`, or `independent`.
`null` when the tier is `co_present`, or when no `GradeProgress` row
exists for this learner+subject (an ungraded subject, or a subject the
learner hasn't been placed into -- treated identically to `co_present`,
`research.md` §3). The frontend caller (`LearnerAssignments.tsx`) stores
this value and, if present, attaches it as `X-Quiz-Handoff-Token` on
every subsequent call for this `quiz_session_id` in place of relying on
the guardian's cookie.

`QuizStartOut` (the response model above) is the **same, shared**
response model `POST /api/quizzes` (spec 005's demo/ad-hoc route) also
returns -- that route's responses gain the same `handoff_token` field,
always `null`, since a non-assignment-linked session never goes through
tier determination at all (FR-014).

## Extended existing routes (spec 011's own extension, further extended)

### `GET /api/quizzes/{quiz_session_id}/next-question` and `POST /api/questions/{question_id}/answer`

Behavior for a `QuizSession` not linked to any `quiz_assignment_targets`
row is unchanged (demo/ad-hoc path, completely unaffected -- same as
spec 011 left it).

For an assignment-linked `QuizSession`, the authorization check (spec
011's `assert_guardian_owns_assignment_session`, renamed
`assert_quiz_session_access`) now also accepts an optional
`X-Quiz-Handoff-Token` request header, evaluated as follows:

1. Determine the tier the same way the start route did (re-derived from
   current `GradeProgress` state, not cached from start time -- a tier
   determined at session start stays fixed for that session's lifetime
   per spec.md's edge case, but re-deriving it is simpler than storing
   it and produces the same answer for the session's duration since
   `unlocked_grade` cannot decrease, spec 017's Monotonicity note).
2. `co_present` or no `GradeProgress` row: unchanged from spec 011 --
   guardian session cookie matching the learner's `guardian_id` is
   required; `X-Quiz-Handoff-Token`, if sent, is ignored.
3. `check_in`, `opt_in_nudges`, or `independent`: the request is
   authorized if *either* the spec-011 guardian check passes, *or* a
   valid `X-Quiz-Handoff-Token` is present whose decoded
   `quiz_session_id` matches the URL/body's `quiz_session_id` and whose
   `QuizSession.status` is still `in_progress`.

Failure modes: `403 not_learner_guardian` (neither guardian session nor
a valid handoff token, unchanged code from spec 011); new `403
invalid_handoff_token` (a handoff token was sent but is expired,
malformed, or scoped to a different `quiz_session_id`); new `409
quiz_session_not_in_progress` (a structurally valid handoff token
presented after its quiz session already reached a terminal status --
FR-005c). No other part of either route's request/response contract
changes.

### `GET /api/quizzes/{quiz_session_id}` (spec 005) -- summary view, called for an assignment attempt (EXTENDED)

Loading a completed/ended-early attempt's summary through this existing
spec-005 route (called from `goToSummary` in `LearnerAssignments.tsx`)
now also sets
`quiz_assignment_targets.guardian_viewed_at` to the current time, the
first time it's called for that target (`research.md` §7). No response
shape change -- this is a side effect of an existing read, not a new
field on it. Idempotent: a second view does not change
`guardian_viewed_at` after it's first set.

### `GET /api/learners/{learner_id}/assignments` (guardian-authenticated) -- list view (EXTENDED)

Response gains one new boolean field per assignment:

```json
{
  "assignments": [
    { "assignment_id": "...", "topic_ids": [...], "question_count": 5,
      "due_at": "...", "cancelled_at": null, "status": "completed",
      "has_unviewed_activity": true }
  ]
}
```

`has_unviewed_activity` is `true` iff **all three** hold: `status` is
`completed` or `ended_early`; `guardian_viewed_at` is still `NULL` for
that target; and the target's current guardian-mediation tier (derived
the same way as the routes above, at read time) is `opt_in_nudges`
(FR-007's in-app indicator, `research.md` §7). `false` in every other
case -- including a `check_in` or `independent` tier target that is
completed and unviewed (FR-006, FR-008: neither of those tiers ever
shows this indicator, only `guardian_viewed_at`'s underlying write is
tier-independent).
