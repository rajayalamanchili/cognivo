# Quickstart: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review

**Feature**: `010-instructor-classroom` | **Date**: 2026-08-23

Validates a full guardian/instructor round trip -- registration through
roster enrollment to a live dashboard and content-review queue --
against the already-deployed Milestones 1-6 backend plus this feature's
new tables and routes. See `data-model.md` for entity detail and
`contracts/api.md` for exact request/response shapes.

## Prerequisites

- Same as `specs/001-domain-agnostic-core/quickstart.md`, plus this
  feature's migration applied (`alembic upgrade head` -- renames
  `demo_learner_profiles` to `learner_profiles`, adds the eight new
  tables).
- `JWT_SECRET` (or equivalent, per `tech-stack.md`'s Authentication
  section) set in the backend's env.

## Validation scenario 1: an instructor and a guardian can each register and sign in

`POST /api/auth/instructor/register` -> `201`, session cookie set.
`POST /api/auth/logout` -> `204`. `POST /api/auth/instructor/login`
with the same credentials -> `201`/`200`, cookie set again. Repeat for
`POST /api/auth/guardian/register`/`login`. Confirm a request to any
instructor-only route without a valid instructor cookie returns `401`.

## Validation scenario 2: same email registers as both a guardian and an instructor

`POST /api/auth/guardian/register` with `parent@example.com` -> `201`.
`POST /api/auth/instructor/register` with the same email -> `201` (not
`409`) -- confirms email uniqueness is scoped per account type
(research.md §2), not global.

## Validation scenario 3: open roster enrollment completes immediately

As an instructor, `POST /api/rosters` with `enrollment_mode: "open"` ->
note the `join_code`. As a guardian, `POST /api/learners` to create a
learner profile, then `POST /api/rosters/join` with that code -> `201`,
`status: "enrolled"`. Confirm `GET /api/rosters/{roster_id}/dashboard`
now lists that learner.

## Validation scenario 4: closed roster enrollment requires approval

As an instructor, `POST /api/rosters` with `enrollment_mode: "closed"`.
As a guardian, join with the code -> `202`, `status: "pending"`.
Confirm the learner does NOT yet appear on the dashboard. As the
instructor, `GET /api/rosters/{roster_id}/requests` -> see the pending
request; `POST .../approve` -> `200`. Confirm the learner now appears
on the dashboard, and the resulting `Enrollment`'s `authorized_by_type`
is `"instructor"` (vs. `"guardian"` for scenario 3's open-roster case).

## Validation scenario 5: unenrollment removes only the roster link

From either scenario above, `DELETE /api/rosters/{roster_id}/enrollments/{learner_id}`
-> `204`. Confirm the learner no longer appears on that roster's
dashboard, but `GET /api/learners/{learner_id}/recommendations` (the
learner's own, pre-existing endpoint) still works identically --
nothing about the learner's account or data changed (SC-007).

## Validation scenario 6: dashboard data matches the learner's own recommendations exactly

Enroll a learner with an existing assessment history (e.g. the
synthetic fixtures from Milestone 2's own test suite) into a roster.
Compare `GET /api/rosters/{roster_id}/dashboard`'s entry for that
learner against `GET /api/learners/{learner_id}/recommendations?subject_id={roster.subject_id}`
called directly -- must be byte-for-byte identical (SC-001).

## Validation scenario 7: cross-tenant isolation

Create two instructors, each with their own roster and enrolled
learner. Confirm instructor A's `GET /api/rosters`, dashboard, and
content-review queue never include instructor B's roster, learners, or
flagged questions, and that a direct `GET /api/rosters/{B's roster_id}/dashboard`
request from instructor A's session returns `403` (SC-002).

## Validation scenario 8: content-review queue is correctly scoped and resolvable

Flag a question via the existing learner-facing
`POST /api/questions/{question_id}/flag` for a learner enrolled in
instructor A's roster. Confirm it appears in instructor A's
`GET /api/content-review/flagged` and NOT in instructor B's. Resolve it
via `POST /api/content-review/{question_id}/resolve` with
`action: "reactivate"` -> confirm it no longer appears in the queue and
`GeneratedQuestion.validation_status` is back to `"valid"` (SC-003).

## Validation scenario 9: real sign-up can never produce a demo account

Attempt `POST /api/auth/guardian/register` with an extra,
client-supplied `is_demo: true` field in the request body -> confirm
the created account still has `is_demo: false` (the field is rejected
or ignored, never honored) -- FR-016, SC-004.

## Validation scenario 10: demo instructor entry point works without real sign-up

`GET /api/demo-instructor` with no session cookie at all -> `200`,
resolves to the seeded `DemoInstructorProfile`. Confirm this profile's
`is_demo` is `true` and it's reachable without ever calling any
`/api/auth/*` route.

Confirm this endpoint also sets a session cookie (`/speckit-clarify`,
Phase 7 implementation) -- unlike the demo-learner endpoint, the demo
instructor needs one to reach any of its actual instructor pages.
Using that cookie: `GET /api/rosters` -> `200` (empty list is fine,
never an error); `POST /api/rosters` -> `201` (confirms
`classroom_rosters.instructor_id` accepts a `DemoInstructorProfile`
id, not only a `RealInstructorAccount` one); `GET /api/rosters/
{roster_id}/dashboard` and `GET /api/content-review/flagged` -> `200`.

## Validation scenario 11: `check_no_real_account_path.py` still passes

Run `uv run python scripts/check_no_real_account_path.py` (or the
pytest wrapper, spec 009 T001-T003) after this feature's models are
added -- confirm it still exits `0`: `RealGuardianAccount`,
`RealInstructorAccount`, and `LearnerProfile` all carry non-nullable
`is_demo`, and `DemoInstructorProfile`'s table name matches the
account-like pattern with `is_demo` also non-nullable.

## Validation scenario 12: Milestones 1-6's full suites still pass

`pytest backend/tests/` (excluding `grading-agent/tests/`) -> 100%
pass, confirming the `demo_learner_profiles` -> `learner_profiles`
rename didn't break any existing MC/numeric/free-text/quiz/
recommendation flow.
