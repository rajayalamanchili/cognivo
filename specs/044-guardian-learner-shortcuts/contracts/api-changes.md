# API Contract Changes: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

Changed backend routes only -- every route below follows this codebase's
existing conventions exactly (FastAPI `APIRouter`, Pydantic request/
response models, the existing `require_learner_ownership_if_real`/
`optional_session_claims` dependencies, the existing `NotFoundError`/
`ConflictError`/`UnprocessableError` error classes) -- no new pattern is
introduced. No new routes; every change below is to an existing endpoint.

## `backend/src/api/routes/learners.py`

### `GET /api/learners/mine` (response shape changed, FR-001)

`MyLearnerOut.enrollment: MyLearnerEnrollmentOut | None` becomes
`MyLearnerOut.enrollments: list[MyLearnerEnrollmentOut]`. Every roster the
learner is enrolled in is now returned (previously: only the first row
the underlying query happened to return, per the `ponytail:` comment
spec 044's Context quotes). `[]` means "not in a class yet" (today's
`None` case). `MyLearnerEnrollmentOut` itself (`roster_id`, `subject_id`,
`grade`) is unchanged.

**Breaking change, same request cycle**: both frontend consumers
(`GuardianLearnerCard.tsx`, the guardian Settings page) are updated in
this same feature -- there is no intermediate state where the backend
ships this change without both consumers already expecting a list.

## `backend/src/api/routes/practice_sessions.py`

### `POST /api/practice-sessions` (FR-008/FR-009)

`PracticeStartIn` gains `learner_id: uuid.UUID | None = None` (optional,
defaults to the demo learner exactly as today when omitted -- every
existing demo-learner call site is unaffected). When provided: resolved
via `require_learner_ownership_if_real(db, learner_id=learner_id,
claims=claims)` (new `claims: SessionClaims | None =
Depends(optional_session_claims)` route dependency); `ForbiddenError` on
a real learner belonging to a different guardian. The existing
`has_placement_data(...)` 404 guard gets `get_next_question`'s own bypass
for a non-demo real learner (research.md §1) -- otherwise unchanged.

### `GET /api/practice-sessions/{practice_session_id}/next-question`, `POST .../end`, `GET /api/practice-sessions/{practice_session_id}` (FR-008)

No new request parameter -- `learner_id` is already resolvable from the
`PracticeSession` row (`practice_session.learner_id`). Each gains the
same `require_learner_ownership_if_real` ownership check using that
already-resolved id, so a guardian can't poll/end/summarize a different
guardian's learner's session by session id alone. `ForbiddenError` on
mismatch; demo-learner sessions behave exactly as today (the check is a
no-op for `learner.is_demo`).

## `backend/src/api/routes/placement.py`

### `POST /api/subjects/{subject_id}/placement/start` (FR-025)

Gains `learner_id: uuid.UUID | None = None` (query param, optional,
same default-to-demo-learner behavior as above) and the identical
`require_learner_ownership_if_real` gate. `submit_placement` and
`skip_placement_question` are **unchanged** -- both already derive
`learner_id` from the `GeneratedQuestion` row a prior `start_placement`
call created (research.md §2).

## `backend/src/api/routes/rosters.py`

### `GET /api/learners/{learner_id}/enrollments` (new response field, FR-024)

`LearnerEnrollmentOut` gains `has_starting_grade: bool`, computed via a
`GradeProgress` existence check for that `(learner_id, subject_id)` --
the same "no second round-trip" precedent `is_default_instructor_roster`
already establishes on this exact response. Lets the frontend decide
whether to offer "Take placement" on a given subject's tile without a
second request. No other field changes; `is_default_instructor_roster`
and the rest of the response are unchanged.

## `backend/src/api/routes/quiz_assignments.py`

### `GET /api/learners/{learner_id}/assignments` (new query param, research.md §3)

Gains `roster_id: uuid.UUID | None = None` (optional query param).
When provided, the existing `QuizAssignmentTarget` ⋈ `QuizAssignment`
query gains `.filter(QuizAssignment.roster_id == roster_id)`. Omitted:
unchanged behavior (every assignment across every enrollment, today's
only behavior). `AssignmentForLearnerOut`'s response shape is unchanged.

## No change

- `submit_placement`, `skip_placement_question` (placement.py) -- already
  learner-agnostic by construction (research.md §2).
- Every other route in `learners.py`, `rosters.py` (roster join/create
  logic, `list_learner_enrollments_route`'s own join itself), and
  `enrollment.py` -- Story 1's multi-enrollment support needed only a
  response-shape change, not a new join path (`Enrollment`'s existing
  `(learner_id, roster_id)` uniqueness already allowed it); Story 5's own
  addition to `rosters.py` (above) is one new field on an existing
  response, not a new join or route.
- Mastery/sequencing/grading endpoints -- untouched by every story in
  this feature.
