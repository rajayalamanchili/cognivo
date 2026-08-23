# Tasks: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review

**Input**: Design documents from `/specs/010-instructor-classroom/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included -- matches this project's existing convention
(every prior milestone ships integration tests alongside the routes
they cover, not as optional polish).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Add `argon2-cffi` and `pyjwt` to `backend/pyproject.toml`'s
      dependencies; `uv sync` (tech-stack.md's Authentication section)
- [X] T002 [P] Document `JWT_SECRET` in `backend/.env.example`
      (research.md §1)

---

## Phase 2: Foundational (blocking prerequisite for every user story)

**⚠️ CRITICAL**: No user story below can be implemented until this
phase is complete -- every story either creates or authenticates
against these tables/utilities.

- [X] T003 Alembic migration in `backend/alembic/versions/`: create
      `real_guardian_accounts`, `real_instructor_accounts`,
      `retention_records` tables first (no FK dependencies on the
      renamed table yet); then rename `demo_learner_profiles` to
      `learner_profiles` and add nullable `guardian_id` (FK ->
      `real_guardian_accounts.guardian_id`) and `retention_record_id`
      (FK -> `retention_records.retention_record_id`) columns; then
      create `classroom_rosters` (with `subject_id` FK -> `subjects`),
      `enrollments`, `enrollment_requests`, `deletion_requests`,
      `demo_instructor_profiles` tables (data-model.md's Correction,
      research.md §3)
- [X] T004 Rename `backend/src/models/demo_learner_profile.py` to
      `learner_profile.py` (`DemoLearnerProfile` -> `LearnerProfile`,
      add `guardian_id`/`retention_record_id` columns matching T003),
      and update every reference across `backend/src/services/
      demo_learner.py`, `backend/src/services/evaluation/conditions.py`,
      `backend/src/models/__init__.py`, `backend/src/api/routes/
      placement.py`, `backend/src/api/routes/demo_learner.py`,
      `backend/src/api/routes/questions.py`, `backend/tests/conftest.py`,
      `backend/tests/unit/test_check_no_real_account_path.py`,
      `backend/tests/integration/evaluation/test_synthetic_data_cleanup.py`,
      `backend/scripts/seed_demo_learner.py` (depends on T003)
- [X] T005 [P] Create `backend/src/models/real_guardian_account.py`
      (data-model.md) (depends on T003)
- [X] T006 [P] Create `backend/src/models/real_instructor_account.py`
      (depends on T003)
- [X] T007 [P] Create `backend/src/models/retention_record.py`
      (depends on T003)
- [X] T008 [P] Create `backend/src/models/classroom_roster.py`
      (includes `subject_id`, `enrollment_mode`, `join_code`) (depends
      on T003)
- [X] T009 [P] Create `backend/src/models/enrollment.py` (depends on
      T003, T004)
- [X] T010 [P] Create `backend/src/models/enrollment_request.py`
      (depends on T003, T004, T008)
- [X] T011 [P] Create `backend/src/models/deletion_request.py`
      (depends on T003)
- [X] T012 [P] Create `backend/src/models/demo_instructor_profile.py`
      (depends on T003)
- [X] T013 [P] Implement `backend/src/services/auth/passwords.py` --
      `hash_password`/`verify_password` via Argon2id (research.md §1)
      (depends on T001)
- [X] T014 [P] Implement `backend/src/services/auth/tokens.py` --
      `issue_token`/`verify_token` via `pyjwt`, claims include account
      type (`guardian`/`instructor`) and id (research.md §1, tech-
      stack.md) (depends on T001, T002)
- [X] T015 Implement `backend/src/services/auth/dependencies.py` --
      FastAPI `Depends()` functions `current_guardian`/
      `current_instructor` that read and verify the session cookie via
      `tokens.py`, raising `401` if missing/invalid/wrong account type
      (depends on T014, T005, T006)

**Checkpoint**: Foundation ready -- every user story below can now be
implemented (and, since each depends only on this phase, in parallel
with each other if staffed).

---

## Phase 3: User Story 1 - An instructor and a guardian can each create an account and sign in (Priority: P1) 🎯 MVP

**Goal**: Register, sign in, stay signed in, sign out -- for both
account types -- and a guardian can add learner profiles.

**Independent Test**: `quickstart.md` scenarios 1, 2, 9.

### Tests for User Story 1

- [X] T016 [P] [US1] Integration test: instructor register/login/logout
      round trip; a protected route rejects a missing/expired session
      (quickstart scenario 1) in
      `backend/tests/integration/test_auth_instructor.py`
- [X] T017 [P] [US1] Integration test: guardian register/login/logout
      + add a learner profile, creating a `RetentionRecord` in the same
      transaction (quickstart scenario 1) in
      `backend/tests/integration/test_auth_guardian.py`
- [X] T018 [P] [US1] Integration test: the same email registers
      successfully as both a guardian and an instructor independently
      (quickstart scenario 2, FR-002a) in
      `backend/tests/integration/test_auth_email_scoping.py`
- [X] T019 [P] [US1] Integration test: a client-supplied `is_demo: true`
      in the register request body is rejected or ignored -- the
      created account always has `is_demo: false` (quickstart scenario
      9, FR-016, SC-004) in
      `backend/tests/integration/test_auth_no_demo_bypass.py`

### Implementation for User Story 1

- [X] T020 [US1] Implement `POST /api/auth/instructor/register` and
      `POST /api/auth/instructor/login` in
      `backend/src/api/routes/auth.py` (depends on T013, T014, T006)
- [X] T021 [US1] Implement `POST /api/auth/guardian/register` and
      `POST /api/auth/guardian/login` in `backend/src/api/routes/auth.py`
      (same file, depends on T020)
- [X] T022 [US1] Implement `POST /api/auth/logout` in
      `backend/src/api/routes/auth.py` (depends on T014)
- [X] T023 [US1] Implement `POST /api/learners` (guardian-authenticated,
      creates a `LearnerProfile` + `RetentionRecord` in one transaction)
      in `backend/src/api/routes/learners.py` (depends on T015, T004,
      T007)
- [X] T024 [US1] Register the `auth` and `learners` routers in
      `backend/src/api/main.py`
- [X] T025 [P] [US1] Guardian and instructor register/sign-in pages in
      `frontend/src/app/(auth)/guardian/` and
      `frontend/src/app/(auth)/instructor/`, plus an "add a learner"
      form on the guardian side (depends on T020-T024)

**Checkpoint**: User Story 1 is fully functional and independently
testable/demoable.

---

## Phase 4: User Story 2 - An instructor creates a classroom roster; a guardian enrolls their child into it (Priority: P1)

**Goal**: Roster creation (open/closed), guardian join (immediate or
pending-approval), instructor approve/decline, and unenrollment by
either side.

**Independent Test**: `quickstart.md` scenarios 3, 4, 5.

### Tests for User Story 2

- [X] T026 [P] [US2] Integration test: open-roster creation and
      immediate guardian join via code (quickstart scenario 3) in
      `backend/tests/integration/test_roster_open_enrollment.py`
- [X] T027 [P] [US2] Integration test: closed-roster join creates a
      pending request; approve creates the `Enrollment` recording the
      instructor as `authorized_by`; decline leaves the learner
      unenrolled (quickstart scenario 4) in
      `backend/tests/integration/test_roster_closed_enrollment.py`
- [X] T028 [P] [US2] Integration test: a second join attempt for the
      same (learner, roster) pair while a request is already pending
      returns the existing pending request, not a duplicate (Edge
      Cases) in `backend/tests/integration/test_roster_duplicate_join.py`
- [X] T029 [P] [US2] Integration test: unenrollment by the guardian and
      separately by the owning instructor each remove only the
      `Enrollment` link -- the learner's account/data are unaffected
      (quickstart scenario 5, SC-007) in
      `backend/tests/integration/test_roster_unenrollment.py`
- [X] T029a [P] [US2] Integration test: instructor A's `GET /api/rosters`
      never includes instructor B's rosters (SC-002's "roster list"
      path, `/speckit-analyze` finding F2) in
      `backend/tests/integration/test_roster_cross_tenant.py`
- [X] T029b [P] [US2] Integration test: a learner can join two
      different rosters (different instructors and/or subjects)
      simultaneously -- confirms two independent `Enrollment` rows
      exist and each roster's enrolled-learner list includes this
      learner with no cross-contamination between rosters (FR-007,
      `/speckit-analyze` finding F3). Deliberately tested at the
      roster/enrollment level, not via the dashboard, so this task has
      no dependency on User Story 3's endpoint. In
      `backend/tests/integration/test_roster_multi_enrollment.py`

### Implementation for User Story 2

- [X] T030 [US2] Implement `backend/src/services/roster/enrollment.py`:
      roster creation/update, open-join (immediate `Enrollment` +
      `authorized_by_type: guardian`), closed-join (creates or returns
      an existing pending `EnrollmentRequest`), approve/decline
      (depends on T008, T009, T010, T015)
- [X] T031 [US2] Implement `POST /api/rosters`, `PATCH
      /api/rosters/{roster_id}`, `GET /api/rosters` in
      `backend/src/api/routes/rosters.py` (depends on T030)
- [X] T032 [US2] Implement `POST /api/rosters/join`, `GET
      /api/rosters/{roster_id}/requests`, `POST .../approve`, `POST
      .../decline` in `backend/src/api/routes/rosters.py` (same file,
      depends on T031)
- [X] T033 [US2] Implement `DELETE
      /api/rosters/{roster_id}/enrollments/{learner_id}` (FR-007a,
      guardian-of-that-learner or the owning instructor only) in
      `backend/src/api/routes/rosters.py` (depends on T032)
- [X] T034 [US2] Register the `rosters` router in `backend/src/api/main.py`
- [X] T035 [P] [US2] Instructor roster-management page (create roster,
      view/approve/decline requests, view enrolled learners with an
      unenroll action) and the guardian-side join-by-code flow in
      `frontend/src/app/instructor/rosters/` (depends on T031-T034)

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - An instructor sees a class-wide weak-area view (Priority: P1)

**Goal**: Dashboard aggregating each enrolled learner's existing,
unmodified Recommendation Agent output.

**Independent Test**: `quickstart.md` scenarios 6, 7.

### Tests for User Story 3

- [ ] T036 [P] [US3] Integration test: dashboard's per-learner data is
      byte-for-byte identical to calling that learner's own
      recommendations endpoint directly (quickstart scenario 6, SC-001)
      in `backend/tests/integration/test_dashboard_aggregation.py`
- [ ] T037 [P] [US3] Integration test: a learner with insufficient
      assessment history is shown with an explicit indicator, never
      omitted or as an error (FR-009) in
      `backend/tests/integration/test_dashboard_insufficient_data.py`
- [ ] T038 [P] [US3] Integration test: instructor A's dashboard never
      includes instructor B's roster/learners; a direct request for
      B's roster from A's session returns `403` (quickstart scenario 7,
      SC-002) in `backend/tests/integration/test_dashboard_cross_tenant.py`

### Implementation for User Story 3

- [ ] T039 [US3] Implement `backend/src/services/dashboard/aggregation.py`
      -- calls `build_weak_area_report` once per learner enrolled in
      the requested roster, no new classification logic (research.md
      §4, FR-008) (depends on T030)
- [ ] T040 [US3] Implement `GET /api/rosters/{roster_id}/dashboard` in
      `backend/src/api/routes/instructor_dashboard.py` (depends on
      T039)
- [ ] T041 [US3] Register the `instructor_dashboard` router in
      `backend/src/api/main.py`
- [ ] T042 [P] [US3] Instructor dashboard page in
      `frontend/src/app/instructor/dashboard/` (depends on T040, T041)

**Checkpoint**: User Stories 1-3 all work independently.

---

## Phase 6: User Story 4 - An instructor reviews and resolves flagged questions (Priority: P2)

**Goal**: Content-review queue scoped to the instructor's own
roster(s), with a reactivate/reject resolution action.

**Independent Test**: `quickstart.md` scenario 8.

### Tests for User Story 4

- [ ] T043 [P] [US4] Integration test: the flagged-question queue is
      scoped via an `Enrollment` join at query time -- a flagged
      question for a learner outside the instructor's roster(s) never
      appears (quickstart scenario 8, FR-011, research.md §5) in
      `backend/tests/integration/test_content_review_scoping.py`
- [ ] T044 [P] [US4] Integration test: resolving a flagged question
      (`reactivate` or `reject`) updates `validation_status`
      accordingly and records an audited event with the resolving
      instructor, action, and timestamp (FR-012/FR-013, SC-003) in
      `backend/tests/integration/test_content_review_resolution.py`

### Implementation for User Story 4

- [ ] T045 [US4] Implement `backend/src/services/content_review/
      resolution.py` -- query flagged `GeneratedQuestion` rows joined
      through `Enrollment` to the requesting instructor's rosters;
      resolve action + audit event (depends on T030, T009)
- [ ] T046 [US4] Implement `GET /api/content-review/flagged`, `POST
      /api/content-review/{question_id}/resolve` in
      `backend/src/api/routes/content_review.py` (depends on T045)
- [ ] T047 [US4] Register the `content_review` router in
      `backend/src/api/main.py`
- [ ] T048 [P] [US4] Instructor content-review queue page in
      `frontend/src/app/instructor/review/` (depends on T046, T047)

**Checkpoint**: User Stories 1-4 all work independently.

---

## Phase 7: User Story 5 - A visitor can try the classroom experience without signing up (Priority: P2)

**Goal**: Seeded demo instructor, reachable without real sign-up,
extending Milestone 1's existing demo-learner pattern.

**Independent Test**: `quickstart.md` scenario 10.

### Tests for User Story 5

- [ ] T049 [P] [US5] Integration test: `GET /api/demo-instructor`
      requires no session cookie and resolves to the seeded
      `DemoInstructorProfile` with `is_demo: true` (quickstart scenario
      10) in `backend/tests/integration/test_demo_instructor.py`

### Implementation for User Story 5

- [ ] T050 [US5] Implement `backend/scripts/seed_demo_instructor.py`,
      mirroring `seed_demo_learner.py`'s pattern (depends on T012)
- [ ] T051 [US5] Implement `GET /api/demo-instructor` in
      `backend/src/api/routes/demo_instructor.py` (depends on T012)
- [ ] T052 [US5] Register the `demo_instructor` router in
      `backend/src/api/main.py`
- [ ] T053 [P] [US5] Extend `frontend/src/app/demo/`'s existing
      demo-learner entry point with a demo-instructor path (depends on
      T051, T052)

**Checkpoint**: All five user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T054 [P] Run `backend/scripts/check_no_real_account_path.py` --
      confirm it still passes with every new model from Phase 2
      (quickstart scenario 11)
- [ ] T055 [P] Run `backend/scripts/check_no_subject_conditionals.py`
      -- confirm no subject-id-keyed conditionals were introduced
      (Constitution Principle III)
- [ ] T056 Regression check: run `backend/tests/` (excluding
      `grading-agent/tests/`) and confirm the full suite still passes
      after the `demo_learner_profiles` -> `learner_profiles` rename
      (quickstart scenario 12, SC-006)
- [ ] T057 Playwright E2E: a full guardian+instructor round trip --
      register both, create a roster, join it, view the dashboard,
      flag and resolve a question -- against the live dev deployment
- [ ] T057a [P] Implement `backend/scripts/reset_demo_data.py`: resets
      `DemoInstructorProfile` and every `LearnerProfile` row with
      `is_demo: true` (plus their mastery state, assessment events,
      generated questions, quiz sessions, and roster
      enrollments/rosters) to a known-good seeded state -- mirrors
      `seed_demo_learner.py`/`seed_demo_instructor.py`'s seed data
      exactly (FR-015, `/speckit-analyze` finding F4)
- [ ] T057b Wire `reset_demo_data.py` to run on a schedule via Vercel
      Cron (`vercel.json`), per `tech-stack.md`'s Demo account reset
      row ("e.g. daily") (FR-015/SC-005, depends on T057a)
- [ ] T057c [P] Integration test: running `reset_demo_data.py` against
      a demo state that's been mutated (e.g. the demo instructor's
      roster has extra enrollments, the demo learner has extra
      assessment events) restores it to exactly the seeded baseline
      (SC-005) in `backend/tests/integration/test_reset_demo_data.py`
- [ ] T058 Update `roadmap.md`'s Milestone 7 status line to record this
      spec's implementation progress

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001-T002)**: No dependencies.
- **Foundational (T003-T015)**: Depends on Setup -- BLOCKS every user
  story. T003 (migration) blocks T004 (model rename) and T005-T012 (new
  models). T013/T014 (password/token utilities) block T015
  (dependencies.py), which every route in every story needs.
- **User Stories (Phase 3-7)**: All depend only on Foundational
  completing -- they may proceed in parallel with each other if
  staffed, or sequentially in priority order (P1 x3, then P2 x2).
- **Polish (Phase 8)**: Depends on all five user stories being
  complete.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories.
- **User Story 2 (P1)**: No dependency on User Story 1's routes, but
  its own tests need a registered guardian/instructor to run against
  (Foundational's auth utilities, not US1's routes specifically).
- **User Story 3 (P1)**: Needs enrolled learners to have anything to
  aggregate -- practically sequenced after User Story 2, though its own
  code has no import-level dependency on US2's route module.
- **User Story 4 (P2)**: Same practical sequencing note as US3 (needs
  enrolled learners and Milestone 1's existing flag endpoint).
- **User Story 5 (P2)**: Fully independent of Stories 1-4.

### Within Each User Story

- Tests written before implementation (this project's existing
  convention).
- Services before routes; routes before router registration; backend
  before the story's frontend page.

## Parallel Example: Foundational Phase

```bash
# After T003 (migration) and T004 (LearnerProfile rename) complete,
# T005-T012 (new model files) touch entirely separate files:
Task: "Create real_guardian_account.py"
Task: "Create real_instructor_account.py"
Task: "Create retention_record.py"
Task: "Create classroom_roster.py"
Task: "Create deletion_request.py"
Task: "Create demo_instructor_profile.py"

# T013/T014 (password/token utilities) are also independent of each
# other and of the model files above:
Task: "Implement services/auth/passwords.py"
Task: "Implement services/auth/tokens.py"
```

## Implementation Strategy

### MVP = User Story 1 (register/sign in/add a learner)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational) -- Foundational
   is unusually large for this project's features because authentication
   and the `LearnerProfile` schema correction are both genuinely
   shared prerequisites, not story-specific work.
2. Complete Phase 3 (User Story 1).
3. **STOP and VALIDATE**: `quickstart.md` scenarios 1, 2, 9.
4. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational -> Foundation ready.
2. User Story 1 -> validate -> deploy (MVP: real accounts exist,
   guardians can add learners).
3. User Story 2 -> validate -> deploy (rosters + enrollment).
4. User Story 3 -> validate -> deploy (the milestone's core value
   proposition: the aggregated dashboard).
5. User Story 4 -> validate -> deploy (content review).
6. User Story 5 -> validate -> deploy (demo accounts round out
   deployability/demoability).
7. Polish.
