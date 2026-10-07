---

description: "Task list for Guardian & Public-Facing UI Redesign"
---

# Tasks: Guardian & Public-Facing UI Redesign

**Input**: Design documents from `/specs/041-guardian-public-ui-redesign/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md (all present)

**Tests**: The spec explicitly scopes new tests to three stories only (SC-002: "no test requiring a behavioral change... except tests newly added for Settings' Account/preference (FR-009/FR-011), the real-learner-session entry point (FR-016/FR-022), and the class directory (FR-017-FR-021)"). Test tasks are therefore included for User Stories 2, 4, and 5 only. User Stories 1 and 3 are restyle/presentational and rely on the existing suite continuing to pass (Polish phase).

**Revised during `/speckit-analyze`**: the original draft of this file had three HIGH findings, all now resolved in spec.md/plan.md/research.md/data-model.md/contracts/api-changes.md before being reflected here:
- **FR-023 added** to spec.md: the guardian-scoped learner-listing endpoint (`GET /api/learners/mine`, T007) that FR-008/FR-010/FR-016/FR-019 all implicitly needed is now an explicit, budgeted requirement (FR-015 updated to match) instead of an undocumented addition.
- **FR-017 revised**: `register_instructor` is no longer required to collect `display_name` (that would have broken ~36 existing test call sites with no real benefit over enforcing it once, at listing time). Enforcement is now solely at the `is_listed`-setting code path, uniform for new and pre-existing instructor accounts, surfaced as an inline prompt on the "List in directory" toggle (T049).
- **FR-022's sign-out guarantee** now has a task (T033) clearing the real-learner session inside `handleSignOut`, and a real mechanism (`password_changed_at` + JWT `iat` comparison, T020/T021) for the Edge Case requiring a changed guardian password to invalidate prior sessions.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md's User Story 1-5

## Path Conventions

Web application: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/` — matches plan.md's Project Structure exactly.

---

## Phase 1: Setup

**Purpose**: Confirm the shared design-token surface the whole redesign draws from before any screen is touched (FR-013).

- [ ] T001 Compare each of the six mockups in `/home/raja/cognivo_home_gaurdian_screens` against `frontend/src/app/globals.css`'s existing spec-027 tokens (`--color-primary`, `--color-primary-subtle`, `--color-surface`, `--color-heading`, `--radius-card: 24px`, Tailwind's native `rounded-full` for pills). Add only genuinely new token values the mockups introduce that none of the above already cover (e.g. a second radius value if any card measures outside 20-28px); do not duplicate an existing token under a new name.

**Checkpoint**: Token system confirmed sufficient (or minimally extended) — all restyle work in Phases 3, 6, and 7 can proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema changes shared by User Stories 2 and 5, plus the new read endpoint FR-023 authorizes. Nothing here blocks User Story 1, 3, or 4 — see Dependencies.

**⚠️ CRITICAL**: User Stories 2 and 5 cannot start until this phase's migration is applied.

- [ ] T002 [P] Add `name: str | None`, `read_aloud_default: bool = False`, `larger_text: bool = False`, `reduce_motion: bool = False`, `theme: str = "system"`, `quiz_finished_email_enabled: bool = True`, `weekly_summary_enabled: bool = False`, and `password_changed_at: datetime | None = None` columns to `RealGuardianAccount` in `backend/src/models/real_guardian_account.py` (data-model.md §`RealGuardianAccount`).
- [ ] T003 [P] Add `display_name: str | None` column to `RealInstructorAccount` in `backend/src/models/real_instructor_account.py` (data-model.md §`RealInstructorAccount`). Not required at registration — see T045/research.md §3.
- [ ] T004 [P] Add `practice_reminders_enabled: bool = False` column to `LearnerProfile` in `backend/src/models/learner_profile.py`, mirroring the existing `career_connections_enabled` column's shape (data-model.md §`LearnerProfile`).
- [ ] T005 [P] Add `is_listed: bool = False` column to `ClassroomRoster` in `backend/src/models/classroom_roster.py` (data-model.md §`ClassroomRoster`).
- [ ] T006 Generate one new Alembic migration in `backend/alembic/versions/` (down_revision = current head `d8e4b5a1f3c7`) adding all eleven new columns from T002-T005 (8+1+1+1) in a single revision, per data-model.md's "one new migration covers all of them." Apply it locally (`alembic upgrade head`) and confirm `alembic_version` advances cleanly.
- [ ] T007 Add `GET /api/learners/mine` (guardian-only, `current_guardian`) in `backend/src/api/routes/learners.py`, returning each `LearnerProfile` where `guardian_id == guardian.guardian_id` as `{learner_id, display_name, enrollment: {roster_id, subject_id, grade} | null}` (FR-023) — the enrollment join mirrors `list_learner_enrollments_route`'s existing `Enrollment`-join pattern in `rosters.py`, extended with `ClassroomRoster.grade`. No pagination (bounded by one guardian's own learner count).

**Checkpoint**: Foundation ready — User Stories 2 and 5 (schema-dependent) and User Stories 1/4 (consumers of T007's listing endpoint) can now proceed.

---

## Phase 3: User Story 1 - Visual redesign with no behavior change (Priority: P1) 🎯 MVP

**Goal**: Home, Sign-in, Try the demo, Guardian · My learners, and Assigned-quiz (start + summary) match the mockups' visual language with zero behavioral regression.

**Independent Test**: Load each screen before/after with identical guardian/instructor/demo state; confirm identical data, navigation, and interactive outcomes (quickstart.md Story 1).

### Implementation for User Story 1

- [ ] T008 [P] [US1] Restyle `frontend/src/app/page.tsx` (Home) to match the Home mockup's palette, typography, spacing, radii, and pill-shaped CTAs — content/links unchanged (FR-001, FR-003).
- [ ] T009 [US1] Collapse `frontend/src/app/sign-in/page.tsx` from a two-link chooser into a single page with a two-way Guardian/Instructor tab switcher, reusing `AuthForm` (`frontend/src/components/AuthForm.tsx`) per tab with each role's existing id-field label, redirect target, contextual note, and registration-availability link (FR-004). Update `frontend/src/app/(auth)/guardian/sign-in/page.tsx` and `frontend/src/app/(auth)/instructor/sign-in/page.tsx` (and their `register` siblings, if any link to them) to redirect into the unified page's correct tab rather than duplicating the form. No Learner tab (Clarifications).
- [ ] T010 [P] [US1] Restyle `frontend/src/app/demo/page.tsx` (Try the demo) to match its mockup — both CTAs' behavior (`enterDemoLearnerMode`, `getDemoInstructor`) unchanged (FR-001, FR-003).
- [ ] T011 [US1] Rebuild `frontend/src/app/(auth)/guardian/learners/page.tsx` from its current single-column list into the mockup's per-learner card dashboard: fetch the guardian's full learner list via `GET /api/learners/mine` (T007) instead of relying solely on session-local `addedLearners`; each enrolled learner's card shows stat tiles (topics mastered, this week, working on) sourced from `mastery-state`/`activity-summary`/`recommendations` for that `learner_id` (FR-008), and a grade-band hand-off explainer. A learner not yet in a class shows "Not in a class yet" (not the mockup's literal "Placement not taken") per Clarifications/Edge Cases, with the existing `JoinRosterForm` still available. "Add a learner" keeps its name-only field (FR-005).
- [ ] T012 [US1] Restyle `frontend/src/components/LearnerAssignments.tsx`'s "not_started" assignment rows (the Assigned-quiz start screen) to match the mockup's stat tiles and hand-off banner layout, rewording the banner to same-device/same-tab continuation language (e.g. "Your guardian started this quiz — continue below") rather than the mockup's literal cross-device framing (FR-006).
- [ ] T013 [US1] Restyle `frontend/src/components/QuizSummary.tsx` (the Assigned-quiz summary screen, also reused by `quiz-flow.tsx`) to match the mockup's visual treatment — score, per-topic/difficulty breakdown, and the existing per-question Met/Missed `AnswerResultView` list unchanged in behavior (FR-001, FR-003).

**Checkpoint**: Run quickstart.md Story 1 steps 1-3 manually (visual parity + join-class/add-learner/start-assignment outcomes unchanged) before moving on.

---

## Phase 4: User Story 2 - Real, persisted guardian Settings (Priority: P1)

**Goal**: A guardian can edit account details, change password, manage preferences, and act on deletion requests from one real Settings page.

**Independent Test**: Edit account details, toggle each preference, reload, confirm persistence; submit a deletion request and confirm it reaches a real pending status (quickstart.md Story 2).

### Tests for User Story 2 ⚠️

- [ ] T014 [P] [US2] Integration tests for `PATCH /api/auth/guardian/me` (name/email edit, email-conflict 409, each preference field) in `backend/tests/integration/test_auth_guardian_settings.py`.
- [ ] T015 [P] [US2] Integration tests for `POST /api/auth/guardian/change-password` in `backend/tests/integration/test_auth_guardian_settings.py`: success, wrong-current-password 401, subsequent login only works with the new password, AND (Edge Cases/FR-022) a session cookie obtained *before* the change is rejected by a protected guardian route on its next use after the change, while a cookie obtained *after* the change keeps working.
- [ ] T016 [P] [US2] Integration test for `PATCH /api/learners/{learner_id}/practice-reminders-preference` (mirrors existing `career-connections-preference` test shape) in `backend/tests/integration/test_auth_guardian_settings.py`.
- [ ] T017 [P] [US2] Extend `backend/tests/integration/test_auth_whoami.py` to cover the guardian-only `name`/preference fields on `WhoAmIOut`.
- [ ] T018 [P] [US2] Frontend unit test in `frontend/tests/unit/guardian-settings.test.tsx` covering account edit+save+reload, password change, each preference toggle's persisted state, and the Privacy & data deletion-request submission + status display.

### Implementation for User Story 2

- [ ] T019 [US2] Add `PATCH /api/auth/guardian/me` in `backend/src/api/routes/auth.py`: optional `name`, `email` (through existing `_normalize_email` + uniqueness check, `ConflictError("email_taken")` on collision), and the six preference fields (`theme` validated as `Literal["system","light","dark"]`). Returns the guardian's full current state.
- [ ] T020 [US2] Add `POST /api/auth/guardian/change-password` in `backend/src/api/routes/auth.py`: verifies `current_password` via existing `verify_password` (`AuthenticationError` on mismatch), re-hashes `new_password` (`min_length=8`) via existing `hash_password`, sets `guardian.password_changed_at = datetime.now(UTC)` (Edge Cases/FR-022, research.md §6), 204 on success.
- [ ] T021 [US2] Extend `backend/src/services/auth/tokens.py`'s `SessionClaims` with an `issued_at: datetime` field, populated in `verify_token` from the JWT's own `iat` claim (already written by `issue_token`, currently decoded and discarded). Extend `backend/src/services/auth/dependencies.py`'s `current_guardian` to raise `AuthenticationError("invalid_session")` when `guardian.password_changed_at is not None and claims.issued_at < guardian.password_changed_at` (research.md §6). This is the mechanism T015's new test exercises.
- [ ] T022 [US2] Add `PATCH /api/learners/{learner_id}/practice-reminders-preference` in `backend/src/api/routes/mastery.py`, directly mirroring `set_career_connections_preference`'s existing shape and `require_learner_ownership_if_real` gate, toggling `LearnerProfile.practice_reminders_enabled`.
- [ ] T023 [US2] Extend `WhoAmIOut`/`whoami()` in `backend/src/api/routes/auth.py` to include `name` and the six preference fields, populated only when `account_type == "guardian"` (same pattern `pending_deletion_warnings` already follows).
- [ ] T024 [US2] Build `frontend/src/app/(auth)/guardian/settings/page.tsx` (new route, new file) with: an Account section (edit name/email, change password, calling T019/T020), a Learners section listing each learner from `GET /api/learners/mine` (name, grade, class — no reset-password control, per FR-010), Display & accessibility toggles and Notifications toggles (calling T019, plus T022 for the per-learner practice-reminders toggle) persisted via `whoami`'s extended read (T023), and a Privacy & data section wiring "delete a learner's data"/"delete my account" to the existing `POST /api/deletion-requests` + `GET /api/deletion-requests/{id}` (spec 020, `backend/src/api/routes/deletion.py`) with real pending/completed status display.
- [ ] T025 [US2] Add a "Settings" link to `GUARDIAN_LINKS` in `frontend/src/components/Nav.tsx`, pointing at `/guardian/settings`.

**Checkpoint**: User Story 1 AND 2 both independently functional. Run quickstart.md Story 2 end-to-end, including signing in on a second client/tab before changing the password and confirming it's logged out on its next request after.

---

## Phase 5: User Story 3 - Mastery before→after on the assigned-quiz summary (Priority: P2)

**Goal**: The Assigned-quiz summary shows each covered topic's mastery before→after, computed client-side from already-fetched data.

**Independent Test**: Complete an assigned quiz; confirm the summary's before→after value matches that topic's first `prior_p_mastery` and last `posterior_p_mastery`, with no new network request (quickstart.md Story 3).

### Implementation for User Story 3

- [ ] T026 [US3] Add a pure client-side aggregation in `frontend/src/components/QuizSummary.tsx` (or a small new helper module alongside it, e.g. `frontend/src/lib/mastery-before-after.ts`) that groups `summary.per_question_results` by `topic_id` and derives each topic's first `prior_p_mastery` and last `posterior_p_mastery`, rendering a before→after row per topic (FR-007). No new fetch — `per_question_results` is already present on `QuizSummaryResponse`.

**Checkpoint**: Manually verify quickstart.md Story 3 (network tab shows no new request beyond the existing summary fetch).

---

## Phase 6: User Story 4 - Real-learner access to Dashboard, Practice, Mastery, AI Tutor (Priority: P2)

**Goal**: A guardian opens one real-learner session per learner from their card, reaching Dashboard/Practice/Mastery/AI Tutor exactly as the demo learner already does, with the demo badge never shown and the session ending cleanly in every exit path.

**Independent Test**: Open a real learner's session from their card; confirm Dashboard/Practice/Mastery/Tutor all stay scoped to that learner with no demo badge; confirm clean session end (return to the learners page, switching learners, AND signing out) with no bleed-through (quickstart.md Story 4).

### Tests for User Story 4 ⚠️

- [ ] T027 [P] [US4] Frontend unit test in `frontend/tests/unit/real-learner-session.test.tsx` covering `enterRealLearnerSession`/`exitRealLearnerSession`/`getRealLearnerSession` (localStorage round-trip + `notifySessionChanged` call) in `frontend/src/lib/visitor-state.ts`.
- [ ] T028 [P] [US4] Extend `frontend/tests/unit/nav.test.tsx` to cover the new `"real-learner"` bucket: real learner's identity shown (not demo badge), `REAL_LEARNER_LINKS` rendered, "Exit learner view" clearing the session and navigating to `/guardian/learners`, AND (FR-022) signing out while a real-learner session is active clears that session too (not just `accountType`/`identifier`).
- [ ] T029 [P] [US4] Extend `frontend/tests/unit/demo-badge.test.tsx` to assert the badge is suppressed while a real-learner session is active, and still shown for the actual demo learner.
- [ ] T030 [P] [US4] Extend `frontend/tests/unit/practice-flow.test.tsx` and `frontend/tests/unit/mastery-flow.test.tsx` to cover the real-learner-session code path (learner resolved from session, not `getDemoLearner()`).

### Implementation for User Story 4

- [ ] T031 [US4] Add `REAL_LEARNER_SESSION_KEY`-backed `getRealLearnerSession`/`enterRealLearnerSession`/`exitRealLearnerSession` to `frontend/src/lib/visitor-state.ts`, mirroring the existing `isDemoLearnerMode`/`enterDemoLearnerMode`/`exitDemoLearnerMode` pattern exactly (research.md §1).
- [ ] T032 [US4] Add a "real-learner" bucket to `bucketFor`/`useVisitorState` in `frontend/src/components/Nav.tsx`, active when `accountType === "guardian"` AND a real-learner session is active; add `REAL_LEARNER_LINKS` (Dashboard, Practice, Mastery, AI Tutor — no Placement) rendered through the existing plain-link branch (not the demo-learner pill branch); show the real learner's identity and an "Exit learner view" action calling `exitRealLearnerSession()` and navigating to `/guardian/learners` (FR-022).
- [ ] T033 [US4] Extend `handleSignOut` in `frontend/src/components/Nav.tsx` to also call `exitRealLearnerSession()` whenever a real-learner session is active, alongside its existing `setAccountType(null)`/`setIdentifier(null)`/`notifySessionChanged()` steps (FR-022 — closes the gap found during `/speckit-analyze`: without this, a stale real-learner identity could survive sign-out and leak into a different guardian's subsequent session on the same browser).
- [ ] T034 [US4] Suppress the badge in `frontend/src/components/DemoBadge.tsx` while a real-learner session is active (check `getRealLearnerSession()` alongside existing `accountType`/`DEMO_LEARNER_PATHNAMES` logic); the demo learner's own badge display is unaffected (FR-022).
- [ ] T035 [P] [US4] Replace `dashboard-flow.tsx`'s unconditional `getDemoLearner()` with real-learner-session awareness (`frontend/src/app/dashboard/dashboard-flow.tsx`): resolve `learnerId` from `getRealLearnerSession()` when active, else fall back to today's demo-learner path.
- [ ] T036 [P] [US4] Same change in `frontend/src/app/practice/practice-flow.tsx`.
- [ ] T037 [P] [US4] Same change in `frontend/src/app/mastery/mastery-flow.tsx`.
- [ ] T038 [P] [US4] Same change in `frontend/src/app/tutor/tutor-flow.tsx`.
- [ ] T039 [US4] Add a session-entry action to each enrolled learner's card on `frontend/src/app/(auth)/guardian/learners/page.tsx` (built in T011) that calls `enterRealLearnerSession(learnerId, displayName)` and navigates to `/dashboard`; omitted for a learner not yet in a class (`needsClass` case, Edge Cases).

**Checkpoint**: User Stories 1, 2, 3, AND 4 all independently functional. Run quickstart.md Story 4 end-to-end, including the two-learners-in-sequence no-bleed-through check AND signing out mid-session.

---

## Phase 7: User Story 5 - Guardian-facing class directory (Priority: P2)

**Goal**: A guardian can browse and join real instructors' publicly-listed, open-enrollment classes without a join code.

**Independent Test**: With at least one listed roster, browse the directory, join, and confirm identical enrollment outcome to a code-based join; confirm closed/unlisted rosters never appear (quickstart.md Story 5).

### Tests for User Story 5 ⚠️

- [ ] T040 [P] [US5] Integration test for `GET /api/rosters/directory` in `backend/tests/integration/test_roster_directory.py`: listed+open rosters appear with subject/grade/instructor display name/join_code; closed rosters never appear regardless of `is_listed`; unlisted open rosters don't appear; empty-directory case.
- [ ] T041 [P] [US5] Integration test for `PATCH /api/rosters/{roster_id}` `is_listed` handling in `backend/tests/integration/test_roster_directory.py`: setting `is_listed=True` on a closed roster raises `cannot_list_closed_roster`; setting it while the owning instructor's `display_name` is unset raises `instructor_display_name_required` (for BOTH a freshly-registered and a pre-existing instructor — no special-casing between them); setting `enrollment_mode=closed` on a listed roster clears `is_listed` as a side effect.
- [ ] T042 [P] [US5] Integration test for `PATCH /api/auth/instructor/me` (display name set, empty-string rejected) in `backend/tests/integration/test_auth_instructor.py`. Confirm the existing `test_instructor_register_login_logout_round_trip` test (and other existing register-instructor call sites in this file) are untouched by this feature — `register_instructor`'s request shape does not change (research.md §3).
- [ ] T043 [P] [US5] Frontend unit test in `frontend/tests/unit/class-directory.test.tsx` covering directory browse/join flow and the empty-state (not error) rendering.
- [ ] T044 [P] [US5] Extend `frontend/tests/unit/rosters-flow.test.tsx` (or create it if absent) to cover the new "List in directory" toggle, including: the disabled/blocked state on a closed roster, AND the inline display-name prompt appearing when the instructor has none set, submitting it, and the toggle becoming usable immediately after.

### Implementation for User Story 5

- [ ] T045 [US5] Add `PATCH /api/auth/instructor/me` in `backend/src/api/routes/auth.py`: instructor-only, required non-empty `display_name` (FR-017), 200 with the updated value. `register_instructor` and `AuthCredentialsIn` are **not** touched — display name is never collected at registration (research.md §3; this avoids the ~36-file test-breakage the original draft of this task would have caused).
- [ ] T046 [US5] Add the `is_listed`-mutual-exclusion helper alongside `update_roster_enrollment_mode` in `backend/src/services/roster/enrollment.py`: reject `is_listed=True` when `enrollment_mode == CLOSED` (`cannot_list_closed_roster`) or when the owning instructor's `display_name IS NULL` (`instructor_display_name_required`) — applied identically regardless of whether the instructor account is new or pre-existing; clear `is_listed` as a side effect when `enrollment_mode` transitions to `CLOSED` (FR-018, data-model.md §Validation rules).
- [ ] T047 [US5] Extend `UpdateRosterIn`/`update_roster_route` in `backend/src/api/routes/rosters.py` to accept optional `is_listed: bool | None`, calling T046's helper.
- [ ] T048 [US5] Add `GET /api/rosters/directory` in `backend/src/api/routes/rosters.py` (guardian-only, `current_guardian`): every `ClassroomRoster` where `is_listed = true AND enrollment_mode = 'open'`, joined to `RealInstructorAccount.display_name`, returning `{roster_id, subject_id, grade, instructor_display_name, join_code}` (FR-019, FR-021). No pagination.
- [ ] T049 [US5] Add a "List in directory" toggle to `frontend/src/app/instructor/rosters/rosters-flow.tsx`, settable only on an open-enrollment roster, calling T047. When the toggle attempt fails with `instructor_display_name_required`, show an inline "Set your display name" field right there, calling T045's `PATCH /api/auth/instructor/me`, then retry the toggle on success (FR-017's unified enforcement point — this is the task that actually gives an instructor a place to set `display_name` at all, since registration no longer collects it). Disable (or auto-clear) the toggle when switching a roster to closed.
- [ ] T050 [US5] Add a class-directory browse UI to `frontend/src/app/(auth)/guardian/learners/page.tsx`'s "join a class" section (alongside the existing `JoinRosterForm` code-entry field, not replacing it): fetch T048's directory, show subject/grade/instructor name per listed roster, and on selection call the *existing* `POST /api/rosters/join` with that roster's `join_code` (FR-020 — no new join request shape). Empty directory renders an empty state, not an error (Edge Cases).

**Checkpoint**: All five user stories independently functional. Run quickstart.md Story 5 end-to-end, including setting a display name for the first time via T049's inline prompt (not at registration).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all five stories together.

- [ ] T051 Run the full existing backend `pytest` suite and frontend `Vitest` suite — expect 100% pass with no behavioral (non-visual-selector) change required outside the newly-added tests from Phases 4, 6, and 7 (SC-002). In particular, confirm every existing instructor-registration test (there are roughly three dozen call sites across the suite) still passes unmodified — T045 deliberately leaves `register_instructor` untouched specifically so this holds.
- [ ] T052 Run the existing Playwright E2E suite against the local deployment — confirm sign-in, class-join, add-learner, start-assignment, and demo-entry flows produce identical functional outcomes to before this feature (SC-006, quickstart.md's Regression check).
- [ ] T053 Side-by-side visual review of all six mockups against their rendered screens (SC-001) — confirm zero unintentional deviations beyond the two clarified departures (no Learner sign-in tab; the reworded hand-off banner).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Independent of Phase 1. Blocks User Story 2 (schema) and User Story 5 (schema) directly; also provides T007 (`GET /api/learners/mine`, FR-023), which User Story 1 (T011) and User Story 4 (T039) consume for the per-learner card list.
- **User Story 1 (Phase 3)**: Needs T001 (tokens) and T007 (learner listing) — not the rest of Phase 2.
- **User Story 2 (Phase 4)**: Needs all of Phase 2 (T002, T006 migration). T021 (session-invalidation wiring) depends on T002's `password_changed_at` column and T020's change-password handler setting it.
- **User Story 3 (Phase 5)**: Needs nothing beyond existing code — independent of Phases 1-2 entirely.
- **User Story 4 (Phase 6)**: Needs T007 (card list) and T011 (card UI) from Phase 3; otherwise independent of Phase 2's schema work. T033 (sign-out clearing) depends on T031/T032 existing first.
- **User Story 5 (Phase 7)**: Needs all of Phase 2 (T003, T005, T006 migration) and T011/T050's card-list UI from Phase 3. T049's inline display-name prompt depends on T045 (the PATCH endpoint) existing first.
- **Polish (Phase 8)**: After all desired stories are complete.

### Parallel Opportunities

- T002-T005 (model column additions, four different files) in parallel.
- T008, T010 (Home, Demo restyles) in parallel; T009, T011-T013 touch shared components/patterns sequentially within Phase 3.
- T014-T018 (US2 tests, mostly one shared new test file plus independent files) — T014/T015/T016 share `test_auth_guardian_settings.py` so run sequentially against each other; T017/T018 are separate files and parallelizable.
- T027-T030 (US4 tests, four separate files) in parallel.
- T035-T038 (four flow components, same mechanical change) in parallel.
- T040-T044 (US5 tests, independent files) in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) → Phase 2's T007 only (the one endpoint US1 needs) → Phase 3 (User Story 1) → **STOP and VALIDATE** against quickstart.md Story 1 → demo-ready restyle with zero behavior change.

### Incremental Delivery

1. Setup + T007 → User Story 1 (MVP restyle) → validate → demo.
2. Rest of Phase 2 (T002-T006) → User Story 2 (real Settings + session invalidation) → validate → demo.
3. User Story 3 (mastery before→after) → validate → demo.
4. User Story 4 (real-learner access) → validate → demo.
5. User Story 5 (class directory) → validate → demo.

Each story adds value without breaking previously-shipped stories, per FR-002/FR-003's "no existing behavior changes" guarantee.
