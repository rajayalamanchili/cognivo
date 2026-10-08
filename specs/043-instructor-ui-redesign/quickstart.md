# Quickstart: Instructor-Facing UI Redesign and Default-Instructor Self-Service

Validation scenarios for this feature, once implemented. Assumes the
usual local dev setup (`backend/`: `uv run uvicorn src.api.main:app
--reload`; `frontend/`: `npm run dev`) against a local/dev `DATABASE_URL`
with migrations applied (`uv run alembic upgrade head`).

## Prerequisites

```bash
# backend/.env (local dev only -- never commit real values)
DEFAULT_INSTRUCTOR_EMAIL=default-instructor@cognivo.internal
DEFAULT_INSTRUCTOR_PASSWORD=<a real password, local-dev value is fine>
DEFAULT_INSTRUCTOR_DISPLAY_NAME=Cognivo   # optional, this is the default

uv run alembic upgrade head   # applies this feature's new migration
```

## Scenario 1 -- Instructor Settings: password change, theme, classroom defaults

1. Register or sign in as a real (non-demo) instructor.
2. `PATCH /api/auth/instructor/me` with `{"theme": "dark",
   "default_enrollment_mode": "closed", "default_due_date_offset_days":
   7}` -- expect `200` with those values echoed back.
3. Open the instructor Settings page in a browser -- expect the page
   to render in dark mode immediately (same mechanism
   `AccountDisplayPreferences.tsx` already uses for a guardian).
4. `POST /api/auth/instructor/change-password` with the current and a
   new password -- expect `204`; sign out and sign back in with the
   new password only.
5. Create a new roster from the Rosters screen with no explicit
   enrollment mode chosen -- expect the create form to start
   pre-filled with "closed" (step 2's default), still overridable
   before submitting.

## Scenario 2 -- Settings: deletion-request entry points

1. As the same instructor, from Settings' Privacy section, request
   deletion of a learner enrolled in one of this instructor's own
   rosters -- expect `202`/`200` from `POST /api/deletion-requests`
   (`target_type: "learner"`), and its status visible via the existing
   deletion-request status check.
2. Request deletion of the instructor's own account
   (`target_type: "instructor"`) -- expect the same success shape.
3. Sign in as the seeded demo instructor and open Settings -- expect
   the persistent demo-account indicator, and both password-change and
   account-deletion controls disabled/hidden.

## Scenario 3 -- Default instructor: always-available class, zero real instructors

1. Run the seed script:
   ```bash
   uv run python scripts/seed_default_instructor.py
   ```
   Expect output confirming the account's `instructor_id` and, for
   every `Subject` row already in the database, one roster created.
   Confirm idempotency by running it again with `--adopt-existing`
   (required on every re-run, not just the first -- Claude Code Review
   finding on PR #111: this script can't tell "our own prior row" apart
   from one that appeared through some other path, e.g. public
   registration, without this explicit opt-in) and seeing zero new
   rosters and the original row's password untouched.
2. As a guardian with a learner that has no real-instructor roster for
   `algebra-1`, call `GET /api/rosters/directory` -- expect a
   `"Cognivo"`-attributed entry for `algebra-1` in the results.
3. Join that roster via the existing `POST /api/rosters/join` flow
   (using the directory entry's `join_code`) -- expect `200`
   `{"status": "enrolled"}`.
4. Call `GET /api/learners/{learner_id}/enrollments` -- expect the new
   entry's `is_default_instructor_roster` to be `true`.
5. Call `POST /api/learners/{learner_id}/rosters/{roster_id}/
   assignments` with a valid `topic_ids` list from `algebra-1` -- expect
   `201` with the same shape the instructor-side endpoint returns.
6. Attempt the same call against a real instructor's own roster (not
   the default instructor's) that this learner is also enrolled in --
   expect `403 not_default_instructor_roster`.
7. Sign in directly with `DEFAULT_INSTRUCTOR_EMAIL`/
   `DEFAULT_INSTRUCTOR_PASSWORD` (the normal instructor login) -- expect
   the Dashboard/Review/Rosters screens to work exactly as they would
   for any other real instructor, including seeing and assigning
   quizzes on the same rosters step 5 used.

## Scenario 4 -- New subject added later

1. Add a new subject's content artifact and run
   `python scripts/load_content_artifact.py content/<new-subject>/
   subject.yaml`.
2. Call `GET /api/rosters/directory` again -- expect a new
   `"Cognivo"`-attributed entry for the new subject's `subject_id`,
   with no manual seeding step beyond loading the content artifact
   itself.
3. Repeat with `DEFAULT_INSTRUCTOR_EMAIL` unset (simulating an
   environment that never seeded a default instructor, e.g. CI) --
   expect the content-artifact load to still succeed, with no roster
   created and no error raised.

## Scenario 5 -- Visual parity (Dashboard/Review/Rosters restyle)

1. Load Dashboard, Review, and Rosters as a real instructor before and
   after the restyle lands, with the same seeded data.
2. Confirm every existing interaction (approve/reject/reactivate a
   flagged question, create/open/close a roster, approve a pending
   join request, assign a quiz) produces an identical outcome --
   only the visual presentation differs (spec.md SC-001/SC-002).
