---

description: "Task list for Instructor-Facing UI Redesign and Default-Instructor Self-Service"
---

# Tasks: Instructor-Facing UI Redesign and Default-Instructor Self-Service

**Input**: Design documents from `/specs/043-instructor-ui-redesign/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md (all present)

**Tests**: Test tasks are included for User Stories 2 and 3 (both introduce real new backend/frontend behavior). User Story 1 is a pure restyle with no behavioral change (spec.md SC-002: "no test requiring a behavioral change") -- it relies on the existing suite continuing to pass, verified in the Polish phase.

**Revised during `/speckit-analyze`**: the original draft of this file had three CRITICAL findings, now resolved:
- **T018 added**: FR-009 requires the Rosters screen's create-roster and assign-quiz forms to pre-fill from the instructor's classroom defaults (quickstart.md Scenario 1 step 5 already assumed this) -- the original draft built Settings' storage side (T014/T015) but never wired the Rosters-side consumption. Everything from the original T018 onward is renumbered by one as a result.
- **spec.md FR-002/FR-009 conflict resolved**: FR-002 now carries an explicit exception for FR-009's pre-fill (mirroring FR-004's own exception pattern), so "interactive outcome unchanged" (US1) and "form starts pre-filled" (US2) no longer contradict each other.
- **spec.md FR-013/Key Entities column count corrected**: both now name all eight new `RealInstructorAccount` columns (including the two lockout columns T003/T004 add), matching research.md/data-model.md/this file instead of underclaiming six.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md's User Story 1-3

## Path Conventions

Web application: `backend/src/`, `backend/tests/`, `frontend/src/`, `frontend/tests/` -- matches plan.md's Project Structure exactly.

---

## Phase 1: Setup

**Purpose**: Confirm the shared design-token surface the restyle draws from, and document the new environment variables the default-instructor seed step needs, before either downstream story begins.

- [X] T001 [P] Compare the four mockups in `/home/raja/cognivo_instructor_screens` against `frontend/src/app/globals.css`'s existing design tokens (established by specs 027/041: `--color-primary`, `--color-surface`, `--radius-card`, Tailwind's native `rounded-full` for pills, etc.). Add only genuinely new token values the mockups introduce that none of the existing tokens already cover; do not duplicate an existing token under a new name.
- [X] T002 [P] Document `DEFAULT_INSTRUCTOR_EMAIL`, `DEFAULT_INSTRUCTOR_PASSWORD`, and `DEFAULT_INSTRUCTOR_DISPLAY_NAME` (optional, defaults to `"Cognivo"`) in `backend/.env.example`, with a comment explaining the seed script that reads them (research.md §5) and that these MUST never be set to real committed values.

**Checkpoint**: Token system confirmed sufficient; env var contract documented. Both downstream phases can proceed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and shared-helper changes User Story 2 needs. Nothing here blocks User Story 1 or User Story 3 -- see Dependencies.

**⚠️ CRITICAL**: User Story 2 cannot start until this phase's migration is applied.

- [X] T003 Add eight new columns to `RealInstructorAccount` in `backend/src/models/real_instructor_account.py` (data-model.md §`RealInstructorAccount`): `theme: str = "system"`, `larger_text: bool = False`, `reduce_motion: bool = False`, `notifications_enabled: bool = True`, `default_enrollment_mode: EnrollmentMode = EnrollmentMode.OPEN`, `default_due_date_offset_days: int | None = None`, `failed_login_attempts: int = 0`, `locked_until: datetime | None = None`.
- [X] T004 [P] In `backend/src/services/auth/lockout.py`: widen `is_locked_out`, `seconds_until_unlocked`, and `record_successful_attempt`'s type hints to a new `AnyRealAccount = RealGuardianAccount | RealInstructorAccount` alias (no behavior change -- both only touch `failed_login_attempts`/`locked_until`). Add a new sibling function `record_failed_attempt_instructor(db: Session, instructor: RealInstructorAccount) -> None`, identical in shape to `record_failed_attempt` but targeting `RealInstructorAccount`/`instructor_id` (research.md §1).
- [X] T005 Generate one new Alembic migration in `backend/alembic/versions/` (down_revision = current head) adding all eight columns from T003, with server defaults matching each column's default above. Apply it locally (`uv run alembic upgrade head`) and confirm `alembic_version` advances cleanly.

**Checkpoint**: Foundation ready -- User Story 2 can now proceed. User Stories 1 and 3 were never blocked by this phase.

---

## Phase 3: User Story 1 - Instructor restyles Dashboard, Review, and Rosters with no behavior change (Priority: P1) 🎯 MVP

**Goal**: Dashboard, Review, and Rosters match their mockups' visual language with zero behavioral regression.

**Independent Test**: Load each screen before/after with identical instructor/demo state; confirm identical data, navigation, and interactive outcomes (quickstart.md Scenario 5).

### Implementation for User Story 1

- [X] T006 [P] [US1] Restyle `frontend/src/app/instructor/dashboard/instructor-dashboard-flow.tsx` to match `InstructorDashboard.dc.html`'s palette, typography, spacing, radii, and component shapes (enrolled-learner count, active-quiz status, class weak-areas list, flagged-questions callout) -- data, navigation targets, and submitted-outcomes unchanged (FR-001, FR-002).
- [X] T007 [P] [US1] Restyle `frontend/src/app/instructor/review/review-flow.tsx` to match `Review.dc.html` (flagged-question queue, approve/reject-with-reason/reactivate actions, "Nothing to review right now" empty state) -- behavior unchanged (FR-001, FR-002).
- [X] T008 [P] [US1] Restyle `frontend/src/app/instructor/rosters/rosters-flow.tsx` to match `Rosters.dc.html` (create roster, class-code copy, who-can-join, pending requests, learner scores/status, assign-a-quiz, open/close) -- submitted-outcomes unchanged (FR-001, FR-002); this does NOT yet include the classroom-defaults pre-fill behavior -- that's T018, landed after this task and after User Story 2's backend fields exist, specifically to avoid the same file being mid-edited by two stories at once.

**Checkpoint**: Run quickstart.md Scenario 5 manually (visual parity + every existing interaction's outcome unchanged) before moving on.

---

## Phase 4: User Story 2 - Instructor manages their account from a new Settings screen (Priority: P1)

**Goal**: An instructor can change their password, set display/notification preferences, set classroom defaults, see what Cognivo stores, request deletions, and see a demo-account indicator -- all from one real Settings page, with those classroom defaults actually pre-filling the Rosters screen's forms.

**Independent Test**: Change password and confirm re-login requires it; toggle each preference and confirm persistence after reload; set a classroom default and confirm a new roster/assignment form starts from it; submit both deletion-request types; confirm a demo instructor sees the badge with password-change/account-deletion disabled (quickstart.md Scenarios 1-2).

### Tests for User Story 2 ⚠️

- [X] T009 [P] [US2] Integration tests for `POST /api/auth/instructor/change-password` in `backend/tests/integration/test_auth_instructor_settings.py`: success (fresh cookie reissued), wrong-current-password 401, demo-account 403, lockout 429 after `LOCKOUT_THRESHOLD` failures.
- [X] T010 [P] [US2] Integration tests for `PATCH /api/auth/instructor/me`'s six new fields in the same file: each field persists independently (`exclude_unset` semantics), `default_due_date_offset_days` rejects a non-positive value with 422, any new field is rejected 403 for a demo-instructor session while a `display_name`-only PATCH still succeeds for one.
- [X] T011 [P] [US2] Extend `backend/tests/integration/test_auth_whoami.py` to cover the new instructor-only fields on `WhoAmIOut` (populated for a real instructor session, `null` for every other session type).
- [X] T012 [P] [US2] Frontend unit test in `frontend/tests/unit/instructor-settings.test.tsx` covering password change, each preference toggle's persisted state, classroom-defaults save, both deletion-request submissions (learner picker scoped to this instructor's own rosters; self), and the demo-account view (badge visible, password-change/account-deletion controls absent or disabled).

### Implementation for User Story 2

- [X] T013 [US2] Add `POST /api/auth/instructor/change-password` in `backend/src/api/routes/auth.py`, mirroring `change_guardian_password` exactly (`ChangePasswordIn`, lockout check via T004's new functions, fresh session cookie reissue on success, `403` for a `DemoInstructorProfile` session) (contracts/api-changes.md §1).
- [X] T014 [US2] Extend `InstructorMeIn`/`InstructorMeOut`/`update_instructor_me` in `backend/src/api/routes/auth.py` with the six new optional fields (`theme` as `Literal["system","light","dark"]`, `default_due_date_offset_days` as `Field(gt=0) | None`), rejecting any of the five non-`display_name` fields with `403` when the session is a `DemoInstructorProfile` (contracts/api-changes.md §2).
- [X] T015 [US2] Extend `WhoAmIOut` and `whoami()` in `backend/src/api/routes/auth.py` with a new `_INSTRUCTOR_ONLY_FIELDS` list (mirroring the existing `_GUARDIAN_ONLY_FIELDS`), populated only for a `RealInstructorAccount` session (contracts/api-changes.md §3).
- [X] T016 [US2] Generalize `frontend/src/components/AccountDisplayPreferences.tsx`'s `refresh()` to branch on `account_type === "guardian" || account_type === "instructor"` (both read identical field names from `WhoAmIOut`) instead of guardian-only (research.md §3).
- [X] T017 [US2] Build the instructor Settings screen: `frontend/src/app/instructor/settings/page.tsx` + `frontend/src/app/instructor/settings/instructor-settings-flow.tsx` (matching the existing per-screen `page.tsx` + `*-flow.tsx` convention), matching `InstructorSettings.dc.html`'s sections -- Account (password change via T013), Classroom defaults (default join policy / default due-date offset via T014), Display (theme/larger-text/reduce-motion via T014/T016), Notifications (toggle via T014, no delivery), Privacy (plain-language what-Cognivo-stores copy; deletion-request forms calling the existing `POST /api/deletion-requests` for a learner picked from this instructor's own rosters' enrollments, and for the instructor's own account), and the persistent demo-account indicator (reusing the existing demo-badge pattern) with password-change/account-deletion hidden or disabled for a demo session.
- [X] T018 [US2] Wire `frontend/src/app/instructor/rosters/rosters-flow.tsx`'s create-roster form and assign-quiz form to pre-fill `enrollment_mode`/`due_at` from the signed-in instructor's `default_enrollment_mode`/`default_due_date_offset_days` (read via `GET /api/auth/whoami`, T015) -- both fields remain fully overridable before submit, and this never retroactively touches an already-created roster or assignment (spec.md FR-009, Edge Cases). Depends on T008 (restyle lands first on this file) and T014/T015 (the fields to read).
- [X] T019 [US2] Add a "Settings" nav link to the instructor nav (shared across Dashboard/Review/Rosters), matching the mockups' nav bar.

**Checkpoint**: Run quickstart.md Scenarios 1-2 manually.

---

## Phase 5: User Story 3 - Guardian enrolls and assigns a quiz with no real instructor involved (Priority: P1)

**Goal**: A seeded, real "default instructor" account always owns one open, listed roster per subject, so a guardian can join one via the existing class directory and self-assign a quiz to their own enrolled learner.

**Independent Test**: Seed the default instructor; confirm its roster appears in the class directory for a subject with zero real-instructor rosters; join it as a guardian; self-assign a quiz; confirm the same assignment is deniable on a non-default-instructor roster; confirm the operator can sign in with the seeded credentials and use the unmodified instructor screens on the same rosters (quickstart.md Scenarios 3-4).

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] Unit tests for `get_default_instructor`/`ensure_default_instructor_roster_for_subject` in `backend/tests/unit/test_default_instructor.py`: `get_default_instructor` returns `None` when `DEFAULT_INSTRUCTOR_EMAIL` is unset or no matching row exists, and the matching row otherwise; `ensure_default_instructor_roster_for_subject` creates exactly one roster per subject, is a no-op on a second call for the same subject (idempotency), and is a no-op (no raise) when no default instructor exists yet.
- [X] T021 [P] [US3] Integration tests for `POST /api/learners/{learner_id}/rosters/{roster_id}/assignments` in `backend/tests/integration/test_guardian_quiz_assignment.py`: success path (response shape matches the instructor-side endpoint's `CreateAssignmentOut`, and the resulting `QUIZ_ASSIGNMENT_CREATED` audit event's `instructor_id` is the default instructor's); `404 unknown_roster_id`; `403 not_your_learner`; `403 not_enrolled`; `403 not_default_instructor_roster` (attempted against a real instructor's own roster the learner is also enrolled in).
- [X] T022 [P] [US3] Integration test extending `backend/tests/integration/test_rosters.py` (or the relevant existing roster test file) for `GET /api/learners/{learner_id}/enrollments`'s new `is_default_instructor_roster` field: `true` for a default-instructor-owned enrollment, `false` for a real instructor's.
- [X] T023 [P] [US3] Frontend unit test for the new guardian "assign a quiz" action (on the learner card for a default-instructor-owned enrollment only) in `frontend/tests/unit/guardian-learners.test.tsx` or the existing equivalent test file.

### Implementation for User Story 3

- [X] T024 [US3] Create `backend/src/services/roster/default_instructor.py` with `get_default_instructor(db)` (env-var email lookup, `None`-safe) and `ensure_default_instructor_roster_for_subject(db, subject_id)` (no-op if no default instructor; otherwise idempotent create-if-absent via the existing `create_roster()`/`update_roster()` services, `enrollment_mode=OPEN`, `is_listed=True`, `grade=None`) (research.md §5).
- [X] T025 [US3] Create `backend/scripts/seed_default_instructor.py`, mirroring `seed_demo_instructor.py`'s idempotent shape: upsert a `RealInstructorAccount` by `DEFAULT_INSTRUCTOR_EMAIL` (hash `DEFAULT_INSTRUCTOR_PASSWORD` via the existing `hash_password`, never re-hashing on an existing row), `is_demo=False`, `display_name` from `DEFAULT_INSTRUCTOR_DISPLAY_NAME` (default `"Cognivo"`), then call T024's `ensure_default_instructor_roster_for_subject` for every existing `Subject` row (depends on T024).
- [X] T026 [US3] Add one call to `ensure_default_instructor_roster_for_subject(db, subject.subject_id)` in `backend/scripts/load_content_artifact.py`, immediately after `persist_content_artifact` (depends on T024).
- [X] T027 [US3] Add `is_default_instructor_roster: bool` to `LearnerEnrollmentOut` and compute it in `list_learner_enrollments_route`, `backend/src/api/routes/rosters.py` (depends on T024) (contracts/api-changes.md §5).
- [X] T028 [US3] Add `POST /api/learners/{learner_id}/rosters/{roster_id}/assignments` in `backend/src/api/routes/rosters.py`: guardian-authenticated, checks (in order) that `roster_id` exists (`404 unknown_roster_id` otherwise), the learner belongs to this guardian, the learner is enrolled in the roster, and the roster is default-instructor-owned (T024), then calls the existing `create_assignment()` unchanged with `instructor_id=roster.instructor_id` and `learner_ids=[learner_id]` (depends on T024) (contracts/api-changes.md §6).
- [X] T029 [US3] Add an "assign a quiz" action to the guardian's learner card (`frontend/src/app/(auth)/guardian/learners/page.tsx` or `frontend/src/components/GuardianLearnerCard.tsx`), shown only when `GET /api/learners/{learner_id}/enrollments` reports `is_default_instructor_roster: true` for that enrollment, calling T028's new endpoint (depends on T027, T028).

**Checkpoint**: Run quickstart.md Scenarios 3-4 manually.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across all three stories.

- [X] T030 [P] Run the full, unfiltered backend (`pytest`) and frontend (`Vitest`) test suites; confirm zero regressions (SC-002) -- no existing test file required a behavioral change to keep passing.
- [ ] T031 Run quickstart.md Scenarios 1-5 end to end manually against a local dev environment with the new migration applied and a seeded default instructor.
- [ ] T032 Run `/code-review` locally (per `CLAUDE.md`'s Polish-phase mandate) before opening the PR; resolve any blocking findings. As part of this pass, explicitly confirm SC-005 by running `grep -rn "notifications_enabled" backend/src` and verifying every match is the PATCH/GET read-write path (T014/T015) and nothing else -- no notification-sending code path exists anywhere in the diff.
- [X] T033 Update `roadmap.md`'s Milestone 25 entry's **Status** line to reflect actual implementation/merge state once this feature ships (per the pattern every other milestone entry already follows) -- do not leave it reading "not yet planned or implemented" after it has been.
- [X] T034 PR #111 review addendum: add `password_changed_at` to `RealInstructorAccount` (ninth column, FR-013 updated) and a new migration; add `instructor_session_revoked` in `backend/src/services/auth/dependencies.py` mirroring `guardian_session_revoked`, wired into `current_session_claims`/`optional_session_claims`; set the column in `change_instructor_password` on every successful change. Closes the session-revocation gap FR-006 originally deferred as an accepted risk -- see spec.md's Edge Cases and research.md §1/§7 for the updated rationale.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion -- BLOCKS User Story 2 only (not US1, not US3).
- **User Story 1 (Phase 3)**: Depends only on Setup (T001). Independent of Phases 2, 4, 5.
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) completion. T018 additionally depends on T008 (same file) and T014/T015 (the fields it reads).
- **User Story 3 (Phase 5)**: Depends only on Setup (T002). Independent of Phases 2, 3, 4.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (User Stories 2 and 3).
- Models/schema before services; services before endpoints; endpoints before frontend consumption.

### Parallel Opportunities

- T001/T002 (Setup) in parallel.
- T004 (Foundational) can run in parallel with T003 (both touch different files; T005's migration depends on T003, not T004).
- Once Setup completes, User Story 1 (Phase 3) and User Story 3 (Phase 5) can proceed fully in parallel with each other and with Phase 2/4 (User Story 2) -- all three stories touch disjoint files except `rosters-flow.tsx` (T008 then T018) and the shared instructor nav bar (T019), which should land after T006-T008 to avoid a merge conflict.
- Within User Story 2: T009-T012 (tests) in parallel; T013/T014/T015 in parallel (same file, `auth.py` -- sequence these three if one engineer, since they share a file despite no logical dependency); T018 strictly after T008 and T014/T015.
- Within User Story 3: T020-T023 (tests) in parallel; T024 before T025/T026/T027/T028 (all depend on it); T025/T026/T027/T028 in parallel once T024 lands (different files).

---

## Parallel Example: User Story 3

```bash
# Launch all tests for User Story 3 together:
Task: "Unit tests for get_default_instructor/ensure_default_instructor_roster_for_subject in backend/tests/unit/test_default_instructor.py"
Task: "Integration tests for POST /api/learners/{learner_id}/rosters/{roster_id}/assignments in backend/tests/integration/test_guardian_quiz_assignment.py"
Task: "Integration test for is_default_instructor_roster in backend/tests/integration/test_rosters.py"
Task: "Frontend unit test for the guardian assign-a-quiz action"

# Once T024 (default_instructor.py) lands, launch its consumers together:
Task: "Create backend/scripts/seed_default_instructor.py"
Task: "Wire ensure_default_instructor_roster_for_subject into load_content_artifact.py"
Task: "Add is_default_instructor_roster to LearnerEnrollmentOut"
Task: "Add POST /api/learners/{learner_id}/rosters/{roster_id}/assignments"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 3: User Story 1 (the pure restyle -- no backend dependency at all).
3. **STOP and VALIDATE**: quickstart.md Scenario 5.
4. Deploy/demo if ready -- this alone matches the three mockups' visual redesign.

### Incremental Delivery

1. Setup → User Story 1 (restyle) → validate → demo.
2. Foundational → User Story 2 (Settings + Rosters pre-fill) → validate → demo.
3. Setup's T002 → User Story 3 (default instructor) → validate → demo.
4. Polish once all three are in.

User Stories 1 and 3 can be built in parallel by different engineers once Setup is done, since they touch fully disjoint files. User Story 2 shares one file (`rosters-flow.tsx`, via T018) with User Story 1 and should sequence its one touch-point (T018) after User Story 1's restyle (T008) lands.
