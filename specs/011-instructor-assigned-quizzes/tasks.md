# Tasks: Instructor-Assigned Quizzes

**Input**: Design documents from `/specs/011-instructor-assigned-quizzes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included -- matches this project's existing convention
(every prior milestone ships integration tests alongside the routes
they cover, not as optional polish; plan.md's Testing section names
every file below explicitly).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [ ] T001 Confirm no new backend/frontend dependencies are required
      (plan.md's Primary Dependencies: none new); create
      `backend/src/services/quiz_assignment/__init__.py`

---

## Phase 2: Foundational (blocking prerequisite for every user story)

**⚠️ CRITICAL**: No user story below can be implemented until this
phase is complete -- every story either creates, targets, or reports on
these tables/enum values.

- [ ] T002 Add `QUIZ_ASSIGNMENT_CREATED`/`QUIZ_ASSIGNMENT_CANCELLED` to
      `AssessmentEventType` in `backend/src/models/enums.py` (FR-015,
      data-model.md's Audit events section)
- [ ] T003 [P] Alembic migration in `backend/alembic/versions/`:
      `ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS
      'quiz_assignment_created'` and `'quiz_assignment_cancelled'`,
      run outside any transaction that also writes a row using either
      value (exact precedent: `5a723b34fc55_content_review_resolved_
      event_type.py`) (depends on T002)
- [ ] T004 Alembic migration in `backend/alembic/versions/`: create
      `quiz_assignments` (`assignment_id` PK, `roster_id` FK ->
      `classroom_rosters`, `instructor_id` FK ->
      `real_instructor_accounts`, `subject_id` FK -> `subjects`,
      `topic_ids` JSON, `question_count`, `due_at` nullable,
      `cancelled_at` nullable, `created_at`) and
      `quiz_assignment_targets` (`assignment_target_id` PK,
      `assignment_id` FK -> `quiz_assignments`, `learner_id` FK ->
      `learner_profiles`, `quiz_session_id` nullable FK ->
      `quiz_sessions`, `created_at`, `UNIQUE (assignment_id,
      learner_id)`) tables (data-model.md)
- [ ] T005 [P] Create `backend/src/models/quiz_assignment.py`
      (data-model.md's QuizAssignment table) (depends on T004)
- [ ] T006 [P] Create `backend/src/models/quiz_assignment_target.py`
      (data-model.md's QuizAssignmentTarget table) (depends on T004)
- [ ] T007 Create `backend/src/services/quiz_assignment/status.py` --
      a pure function deriving `not_started`/`in_progress`/`completed`/
      `ended_early` from a target's `quiz_session_id`/linked
      `QuizSession.status` (data-model.md's derived-status table),
      shared by User Story 2's guardian list and User Story 3's
      per-student report (depends on T005, T006)

**Checkpoint**: Foundation ready -- User Stories 1 and 2's
*implementation* (T010-T016, T023-T028) can now proceed in parallel (if
staffed); User Story 2's own *tests* (T017-T021) need User Story 1's
T010 to have run first to create a fixture assignment to act on (see
Dependencies section below), and User Story 3 additionally depends on
User Story 1 having assignments to report on.

---

## Phase 3: User Story 1 - Instructor assigns a quiz to a chosen subset of a roster (Priority: P1) 🎯 MVP

**Goal**: An instructor picks topic(s), a question count, an optional
due date, and a subset (or all) of a roster's enrolled learners, and
the assignment is created and visible.

**Independent Test**: `quickstart.md` scenario 1 (and scenario 7's
creation-audit-event assertion).

### Tests for User Story 1

- [ ] T008 [P] [US1] Unit test for target-list resolution (subset vs.
      `"all"`, empty-target rejection) in `backend/tests/unit/
      test_quiz_assignment_target_resolution.py` (FR-002, FR-003)
- [ ] T009 [P] [US1] Integration test: assignment creation (subset
      targeting, `"all"` targeting, cross-tenant rejection, an enrolled-
      after-creation learner not retroactively targeted, invalid/
      cross-subject `topic_ids` rejected, one `QUIZ_ASSIGNMENT_CREATED`
      event written per targeted learner) in `backend/tests/
      integration/test_quiz_assignment_create.py` (FR-001-FR-005,
      FR-015; `quickstart.md` scenarios 1, 7)

### Implementation for User Story 1

- [ ] T010 [US1] Implement `resolve_target_learner_ids()` and
      `create_assignment()` in `backend/src/services/quiz_assignment/
      assignment.py` -- validates `topic_ids` all belong to one subject
      matching the roster's own `subject_id` (mirrors `quiz.py`'s
      `_resolve_quiz_subject_id`), resolves subset vs. `"all"` against
      current `Enrollment` rows, rejects an empty resulting target list,
      writes one `QuizAssignment` row, one `QuizAssignmentTarget` row
      per targeted learner, and one `QUIZ_ASSIGNMENT_CREATED`
      `AssessmentEvent` per targeted learner via the existing
      `record_event()` (FR-001-FR-005, FR-015, research.md §1/§4/§7)
      (depends on T003, T005, T006)
- [ ] T011 [US1] Implement `cancel_assignment()` in `backend/src/
      services/quiz_assignment/assignment.py` -- sets `cancelled_at`,
      rejects if already cancelled, writes one `QUIZ_ASSIGNMENT_
      CANCELLED` event per target row not yet `completed` (FR-012,
      FR-015, research.md §6/§7) (depends on T010)
- [ ] T012 [US1] Add `POST /api/rosters/{roster_id}/assignments`,
      `GET /api/rosters/{roster_id}/assignments`, and `DELETE
      /api/rosters/{roster_id}/assignments/{assignment_id}` routes in
      `backend/src/api/routes/quiz_assignments.py`, gated by
      `current_instructor` plus an owner-only check mirroring
      `rosters.py`'s `_get_owned_roster` (contracts/api.md) (depends on
      T010, T011)
- [ ] T013 [US1] Register the new router:
      `app.include_router(quiz_assignments.router)` in
      `backend/src/api/main.py` (depends on T012)
- [ ] T014 [P] [US1] Add `createAssignment`, `listRosterAssignments`,
      `cancelAssignment` client functions in
      `frontend/src/services/api.ts` (contracts/api.md) (depends on
      T012)
- [ ] T015 [US1] Extend `frontend/src/app/instructor/rosters/
      rosters-flow.tsx` with an "assign a quiz" form (topic(s),
      question count, optional due date, subset/all learner selection)
      and a per-roster assignment list (depends on T014)
- [ ] T016 [P] [US1] Vitest test for the assignment-creation form in
      `frontend/tests/unit/rosters-flow.test.tsx` -- confirms subset/
      `"all"` targeting and empty-target validation (depends on T015)

**Checkpoint**: User Story 1 is independently functional -- an
instructor can create, list, and cancel assignments end to end. (A
guardian cannot yet act on one; that's User Story 2.)

---

## Phase 4: User Story 2 - A guardian starts an assigned quiz on behalf of their learner (Priority: P1)

**Goal**: The guardian of a targeted learner starts and continues that
learner's assigned-quiz attempt from their own session, with identical
difficulty-adaptation and mastery-update behavior to a self-serve quiz.

**Independent Test**: `quickstart.md` scenarios 2, 3, 4, 6 (and
scenario 5's guardian-visibility assertion, and scenario 7's
in-flight-completion assertion).

### Tests for User Story 2

- [ ] T017 [P] [US2] Integration test: guardian starts/continues an
      assigned attempt; non-owning-guardian and not-targeted rejections
      on start and on the two extended continuation routes in
      `backend/tests/integration/test_quiz_assignment_start_
      authorization.py` (FR-006, FR-013; `quickstart.md` scenario 3)
- [ ] T018 [P] [US2] Integration test: single-attempt enforcement,
      including a concurrent double-start race (mirrors
      `test_roster_duplicate_join.py`'s existing pattern) in
      `backend/tests/integration/test_quiz_assignment_single_
      attempt.py` (FR-014; `quickstart.md` scenario 4)
- [ ] T019 [P] [US2] Integration test: a past due date blocks a new
      start but an already-in-progress attempt is allowed to finish in
      `backend/tests/integration/test_quiz_assignment_due_date.py`
      (FR-014; `quickstart.md` scenario 4)
- [ ] T020 [P] [US2] Integration test: a learner unenrolled from the
      roster after being targeted is blocked from starting in
      `backend/tests/integration/test_quiz_assignment_unenrollment.py`
      (FR-011; `quickstart.md` scenario 6)
- [ ] T021 [P] [US2] Integration test: an assigned quiz's difficulty-
      adaptation and grading/mastery-update behavior is identical to a
      non-assigned quiz given the same scripted answer sequence, in
      `backend/tests/integration/test_quiz_assignment_mastery_
      parity.py` (FR-007, FR-008; SC-002's hard gate)
- [ ] T022 [US2] Integration test: cancellation never retracts a
      completed attempt's mastery data, a cancelled assignment still
      appears (marked cancelled) in the guardian's list, and an attempt
      already in progress at cancellation still reports `completed`
      with a real score once finished, in `backend/tests/integration/
      test_quiz_assignment_cancellation.py` (FR-012, FR-016;
      `quickstart.md` scenarios 5, 7) (depends on User Story 1's T011/
      T012 and this phase's T023/T024)

### Implementation for User Story 2

- [ ] T023 [US2] Implement start-eligibility checks (targeted,
      not-already-attempted, not-past-due, not-cancelled, still-
      enrolled) and `start_assignment_attempt()` in `backend/src/
      services/quiz_assignment/assignment.py` -- calls the existing
      `start_quiz()`/`generate_quiz_question()` unchanged and sets
      `quiz_assignment_targets.quiz_session_id` in the same transaction
      (FR-006, FR-011, FR-014, research.md §1/§2/§3) (depends on T005,
      T006)
- [ ] T024 [US2] Add `GET /api/learners/{learner_id}/assignments`
      (includes cancelled assignments, FR-016, using T007's status
      helper) and `POST /api/assignments/{assignment_id}/learners/
      {learner_id}/start` routes in `backend/src/api/routes/
      quiz_assignments.py`, gated by `current_guardian` plus an
      own-learner check mirroring `learners.py` (contracts/api.md)
      (depends on T023, T007)
- [ ] T025 [US2] Extend `GET /api/quizzes/{quiz_session_id}/next-
      question` (`backend/src/api/routes/quiz.py`) and `POST
      /api/questions/{question_id}/answer` (`backend/src/api/routes/
      questions.py`) with the conditional guardian-ownership check for
      an assignment-linked session (research.md §2) -- no behavior
      change when the session is not assignment-linked (depends on
      T023)
- [ ] T026 [P] [US2] Add `listLearnerAssignments`, `startAssignment`
      client functions in `frontend/src/services/api.ts`
      (contracts/api.md) (depends on T024)
- [ ] T027 [US2] Create `frontend/src/components/
      LearnerAssignments.tsx` -- a per-learner assignment list (status,
      due date, cancelled badge) with a "start" action, rendered from
      `frontend/src/app/(auth)/guardian/learners/page.tsx`, reusing
      `frontend/src/app/quiz/quiz-flow.tsx`'s existing question/answer
      UI for an in-progress attempt (depends on T026)
- [ ] T028 [P] [US2] Vitest test for `LearnerAssignments.tsx` (not-
      started/in-progress/completed/cancelled rendering, start action)
      in `frontend/tests/unit/learner-assignments.test.tsx` (depends on
      T027)

**Checkpoint**: User Stories 1 and 2 are both independently functional
-- the full assign-and-take round trip works end to end. (Per-student
reporting beyond the create-time response comes next.)

---

## Phase 5: User Story 3 - Instructor reviews per-student assignment results (Priority: P2)

**Goal**: An instructor sees each targeted learner's individual status
and score for a given assignment, not a class-wide aggregate.

**Independent Test**: `quickstart.md` scenario 8 (a mixed-status
per-student report), plus scenario 1's per-student-view portion.

### Tests for User Story 3

- [ ] T029 [P] [US3] Integration test: per-assignment report shows the
      correct status and score for a mix of not_started/in_progress/
      completed/ended_early learners in `backend/tests/integration/
      test_quiz_assignment_report.py` (FR-009, FR-010)

### Implementation for User Story 3

- [ ] T030 [US3] Add `GET /api/rosters/{roster_id}/assignments/
      {assignment_id}` route in `backend/src/api/routes/
      quiz_assignments.py`, using T007's status helper plus the
      existing `compute_quiz_summary()` for a completed attempt's score
      (FR-009, FR-010, contracts/api.md) (depends on T007, T010)
- [ ] T031 [P] [US3] Add `getAssignmentDetail` client function in
      `frontend/src/services/api.ts` (contracts/api.md) (depends on
      T030)
- [ ] T032 [US3] Extend `frontend/src/app/instructor/rosters/
      rosters-flow.tsx` with a per-assignment results view (a table of
      targeted learners' status/score) (depends on T031, T015)
- [ ] T033 [P] [US3] Vitest test for the per-assignment results view in
      `frontend/tests/unit/rosters-flow.test.tsx` (depends on T032)

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Playwright E2E: assign -> guardian starts and completes
      -> instructor views the per-student result, extending
      `instructor-classroom-round-trip.spec.ts`'s pattern, in
      `frontend/tests/e2e/instructor-assigned-quiz-round-trip.spec.ts`
      (quickstart.md, full round trip)
- [ ] T035 Run the full backend regression suite (`uv run pytest`) and
      `check_no_subject_conditionals.py` -- confirm no regression in
      Milestones 1-7's suites (plan.md's Constitution Check, Principle
      III)
- [ ] T036 Update `roadmap.md`'s Milestone 8 status line to reflect
      `/speckit-implement` completion, in the same commit that
      completes it
- [ ] T037 Run `quickstart.md`'s 8 validation scenarios end to end
      against a real migrated dev database

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- can start immediately.
- **Foundational (Phase 2)**: Depends on Setup -- BLOCKS all user
  stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only.
- **User Story 2 (Phase 4)**: Its *code* (T023-T028) depends on
  Foundational only. Its *tests* (T017-T021) additionally depend on
  User Story 1's T010 (`create_assignment()`) to have any
  `QuizAssignment`/`QuizAssignmentTarget` row to act on -- this
  codebase's existing convention (`test_quiz_next_question.py`,
  `test_quiz_summary.py`) is fixture setup via the real service
  function/route, not raw ORM inserts, so this is a genuine test-level
  dependency, not just an implementation nicety. In practice this means
  User Story 1's T010 (not the full T012-T016 route/UI work) is a
  practical prerequisite for running User Story 2's test suite, even
  though User Story 2's own *feature* is conceptually independent. Its
  cancellation test (T022) additionally depends on User Story 1's
  T011/T012 (the cancel endpoint).
- **User Story 3 (Phase 5)**: Depends on Foundational (T007) and User
  Story 1 (T010, needs assignments to exist to report on).
- **Polish (Phase 6)**: Depends on all three user stories.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on User Story 2 or 3 for its own
  independent test (`quickstart.md` scenario 1's creation half).
- **User Story 2 (P1)**: Independently testable via `quickstart.md`
  scenarios 2-4, 6 without User Story 1's cancel/list UI; only its own
  cancellation test (T022) needs User Story 1's cancel endpoint.
- **User Story 3 (P2)**: Needs User Story 1's assignments to exist as
  data to report on -- not independently testable in isolation the way
  1 and 2 are, since it has nothing to display without them.

### Within Each User Story

- Tests MUST be written and FAIL before implementation.
- Models/migrations (Foundational) before services.
- Services before routes.
- Routes before frontend API client functions.
- Client functions before UI components.

### Parallel Opportunities

- T005/T006 (models) in parallel once T004 (migration) lands.
- All of T008/T009 (User Story 1 tests) in parallel.
- All of T017-T021 (User Story 2 tests) in parallel.
- T014 (User Story 1) and T026 (User Story 2) frontend API-client
  additions touch the same file (`frontend/src/services/api.ts`) --
  do NOT run in parallel with each other despite both being marked
  `[P]` relative to their own story; sequence them if working the same
  session.
- User Story 1 and User Story 2's backend implementation (T010-T013 vs.
  T023-T025) can proceed in parallel by different developers once
  Foundational is complete -- they touch different functions in the
  same new `assignment.py`/`quiz_assignments.py` files, so coordinate
  if staffed concurrently.

---

## Parallel Example: User Story 1

```bash
# Launch User Story 1's tests together:
Task: "Unit test for target-list resolution in backend/tests/unit/test_quiz_assignment_target_resolution.py"
Task: "Integration test for assignment creation in backend/tests/integration/test_quiz_assignment_create.py"

# Launch the two new models together (after T004's migration lands):
Task: "Create backend/src/models/quiz_assignment.py"
Task: "Create backend/src/models/quiz_assignment_target.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL -- blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: `quickstart.md` scenario 1.
5. Deploy/demo if ready -- an instructor can configure and see
   assignments exist, even before any learner can take one.

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready.
2. Add User Story 1 -> validate -> deploy/demo (MVP).
3. Add User Story 2 -> validate (`quickstart.md` scenarios 2-6) ->
   deploy/demo -- the full assign-and-take round trip now works.
4. Add User Story 3 -> validate -> deploy/demo -- instructors can now
   see per-student results, not just an aggregate.
5. Polish: E2E coverage, full regression pass, `roadmap.md` status,
   live quickstart validation.
