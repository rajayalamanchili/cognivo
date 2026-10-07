# Quickstart: Guardian & Public-Facing UI Redesign

Validation scenarios proving each user story end-to-end. Run after
`/speckit-implement`, against a local dev environment with the new
migration applied (`alembic upgrade head`).

## Prerequisites

- `backend/` running locally (`uvicorn` dev server) with the new migration applied.
- `frontend/` running locally (`next dev`).
- At least one real guardian account (register via `/sign-in` → Guardian tab → "Create a guardian account") with at least one added learner.
- At least one real instructor account, for User Story 5.

## Story 1 -- Visual parity (restyle, no behavior change)

1. Load Home, Try the demo, Guardian · My learners, and Assigned-quiz (both start and summary states) and compare side-by-side against the six mockups in `/home/raja/cognivo_home_gaurdian_screens` -- colors, type, spacing, radii, and button/nav shapes should match.
2. Load `/sign-in` -- confirm it is a single page with a two-way Guardian/Instructor tab switcher (no Learner tab), and that switching tabs updates the id-field label, note, and submit behavior exactly as today's separate pages did.
3. As a guardian, join a class, add a learner, and start an assigned quiz -- confirm every outcome (roster state, learner list, quiz session start) is unchanged from pre-redesign behavior.
4. Run the full existing Vitest + pytest suites -- expect 100% pass with no behavioral (non-visual-selector) change required, per SC-002.

## Story 2 -- Guardian Settings is real, not decorative

1. Sign in as a guardian, open `/guardian/settings`.
2. Edit name and email, save, reload the page -- confirm both persisted.
3. Change password, sign out, sign back in with the *new* password only -- confirm the old password no longer works.
4. Toggle each Display/Notification preference, reload -- confirm every toggle state persisted.
5. From Privacy & data, request deletion of a learner -- confirm it shows a real "Pending" status sourced from the existing spec 020 deletion-request API (check `GET /api/deletion-requests` directly if needed).
6. Confirm the "Add a learner" form on Guardian · My learners still only asks for a name -- no username/password fields.

## Story 3 -- Mastery before→after on the assigned-quiz summary

1. As a guardian, start an assigned quiz for a learner covering a known topic; complete it.
2. On the summary screen, confirm each covered topic shows a before→after mastery percentage.
3. Open browser dev tools' network tab while loading the summary -- confirm no network request fires beyond what the summary screen already made before this feature (SC-005).

## Story 4 -- Real-learner access to Dashboard, Practice, Mastery, AI Tutor

1. As a guardian with an enrolled real learner, open that learner's session from their card on Guardian · My learners.
2. Confirm Dashboard renders that real learner's own mastery/activity data (not the demo learner's -- check the displayed name/topics against what you'd expect for that specific learner).
3. Navigate to Practice, Mastery, and AI Tutor via the nav -- confirm each stays scoped to the same real learner.
4. Confirm the demo-account badge is **not** shown on any of these four pages during this session.
5. Return to Guardian · My learners, then open a *different* learner's session -- confirm no data or identity from the first learner persists into the second.
6. Separately, load `/dashboard` (or `/practice`, `/mastery`, `/tutor`) as the actual demo learner (via `/demo` → "Try as a demo learner") -- confirm the demo badge **is** still shown there, unaffected by this feature.

## Story 5 -- Class directory

1. As a real instructor, set a display name (`PATCH /api/auth/instructor/me` or its Settings-equivalent UI control), create an open-enrollment roster, and set it to "listed."
2. As a guardian with a learner not yet in a class, open "join a class" on Guardian · My learners -- confirm the listed roster appears with its subject, grade, and the instructor's display name, with no join code shown.
3. Select it and confirm -- confirm the learner is enrolled, with the same outcome `POST /api/rosters/join` already produces for a manually-typed code.
4. As the instructor, close the roster (set `enrollment_mode=closed`) -- confirm it disappears from the directory and `is_listed` was cleared.
5. As a guardian with no listed rosters visible, confirm the directory renders an empty state, not an error, and the manual code-entry field is still present and functional.

## Regression check

Run the full existing Playwright E2E suite against the local deployment --
expect the existing sign-in, class-join, add-learner, start-assignment,
and demo-entry flows (SC-006) to produce identical functional outcomes to
before this feature.
