# Quickstart: Instructor-Assigned Quizzes

**Feature**: `011-instructor-assigned-quizzes` | **Date**: 2026-08-23

Validates the full assign -> guardian-mediated attempt -> per-student
reporting round trip against the already-deployed Milestones 1-7
backend plus this feature's two new tables and routes. See
`data-model.md` for entity detail and `contracts/api.md` for exact
request/response shapes.

## Prerequisites

- Same as `specs/010-instructor-classroom/quickstart.md`, plus this
  feature's migration applied (`alembic upgrade head` -- adds
  `quiz_assignments` and `quiz_assignment_targets`).
- An instructor account with an open roster containing at least two
  enrolled learners, each with a distinct guardian account (follow
  `specs/010-instructor-classroom/quickstart.md` scenarios 1 and 3
  twice to set this up).

## Validation scenario 1: instructor assigns a quiz to a subset of the roster

As the instructor, `POST /api/rosters/{roster_id}/assignments` with
`topic_ids`, `question_count`, and `learner_ids` set to only one of the
two enrolled learners (learner A). Confirm `201` with `target_learner_
ids` containing exactly learner A. `GET /api/rosters/{roster_id}/
assignments/{assignment_id}` shows learner A as `not_started`; learner B
does not appear in `learners` at all (never targeted).

## Validation scenario 2: a targeted learner's guardian completes the assignment identically to a self-serve quiz

As learner A's guardian, `GET /api/learners/{learner_A_id}/assignments`
-> confirms the assignment appears with `status: "not_started"`.
`POST /api/assignments/{assignment_id}/learners/{learner_A_id}/start`
-> `201` with a first question, same shape as `POST /api/quizzes`
(spec 005). Answer each question via the existing `POST /api/questions/
{question_id}/answer` and fetch subsequent questions via the existing
`GET /api/quizzes/{quiz_session_id}/next-question`, exactly as spec
005's own quickstart does. Confirm each answer updates
`GET /api/learners/{learner_A_id}/mastery-state` (spec 001) identically
to a non-assigned quiz answer. On completion, confirm
`GET /api/rosters/{roster_id}/assignments/{assignment_id}` now shows
learner A as `completed` with a matching score.

## Validation scenario 3: only the targeted learner's own guardian can start or continue

As learner B's guardian (not targeted), attempt
`POST /api/assignments/{assignment_id}/learners/{learner_A_id}/start`
-> `403 not_your_learner`. As learner A's guardian, attempt to start the
same assignment for learner B -> `403 not_targeted`. As a guardian who
is not learner A's own guardian, attempt
`GET /api/quizzes/{quiz_session_id}/next-question` for learner A's
in-progress assignment session -> `403 not_learner_guardian`.

## Validation scenario 4: single attempt and due-date enforcement

Repeat scenario 1's `POST .../start` for learner A (already completed
in scenario 2) -> `409 already_attempted`. Create a second assignment
with `due_at` in the past -> as the targeted learner's guardian,
`POST .../start` -> `409 past_due`.

## Validation scenario 5: instructor cancellation doesn't touch recorded mastery data, and stays visible to the guardian

Create a third assignment targeting learner B, `DELETE
/api/rosters/{roster_id}/assignments/{assignment_id}` before learner B
starts it -> `204`. Confirm learner B's guardian can no longer start it
(`409 assignment_cancelled`), but `GET /api/learners/{learner_B_id}/
assignments` still lists it, now with `cancelled_at` set (FR-016) --
not omitted from the response. Re-run scenario 2's mastery-state check
for learner A's already-completed assignment from scenario 1 -> values
unchanged by the unrelated cancellation.

## Validation scenario 6: unenrollment blocks a not-yet-started target

Create a fourth assignment targeting learner B; as the instructor,
unenroll learner B from the roster (`DELETE /api/rosters/{roster_id}/
enrollments/{learner_B_id}`, spec 010). As learner B's guardian, attempt
`POST .../start` for that assignment -> `403 not_enrolled`.

## Validation scenario 7: assignment creation/cancellation are audited, and an in-flight attempt still counts after cancellation

After scenario 1's `POST /api/rosters/{roster_id}/assignments`, confirm
a `QUIZ_ASSIGNMENT_CREATED` `AssessmentEvent` row exists for learner A
(FR-015). Create a fifth assignment targeting a third enrolled learner
(learner C); as learner C's guardian, start it (attempt now
`in_progress`); as the instructor, cancel the assignment -> confirm a
`QUIZ_ASSIGNMENT_CANCELLED` event is recorded for learner C (their
attempt hadn't completed yet). As learner C's guardian, finish the
already-started attempt -> confirm `GET /api/rosters/{roster_id}/
assignments/{assignment_id}` still shows learner C as `completed` with
a real score, even though the assignment is cancelled (FR-012).
