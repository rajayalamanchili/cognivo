---

description: "Task list for Real-Account Deletion Pathway"
---

# Tasks: Real-Account Deletion Pathway

**Input**: Design documents from `specs/020-deletion-pathway/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included per this repo's established convention (every prior
milestone's `tasks.md` writes unit/integration tests alongside
implementation, matched to specific FR/SC IDs).

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3)
to enable independent implementation and testing of each.

## Phase 1: Setup

No new project, service, or dependency, and no new table/column
(plan.md's Structure Decision, data-model.md) -- this feature extends
the existing `backend` in place. Nothing to do here beyond what
Foundational already covers.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared plumbing every user story's endpoints and cron
logic depend on -- error type, authorization rules, and the cascade
executor's dependency-order table walk itself.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T001 [P] Add `DeletionAlreadyPendingError` (409, carries `deletion_request_id`) to `backend/src/api/errors.py`, and its handler in `backend/src/api/main.py` returning `{"error": "deletion_already_pending", "deletion_request_id": str(exc.deletion_request_id)}` (contracts/api.md)
- [ ] T002 [P] Create `backend/src/services/deletion/__init__.py` (empty package init)
- [ ] T003 [US1][US2] Implement `backend/src/services/deletion/authorization.py`: `can_request_deletion(requester_claims, target_type, target_id, db) -> bool` per contracts/api.md's authorization table (guardian → self or own linked learner; instructor → self or a learner enrolled in one of their rosters) (depends on T002)
- [ ] T004 [P] Unit tests for `authorization.py` in `backend/tests/unit/test_deletion_authorization.py`: guardian may target self and their own linked learner; guardian may NOT target an unrelated learner or an instructor; instructor may target self and a learner in one of their rosters; instructor may NOT target a learner outside every roster they own (depends on T003)
- [ ] T005 Implement `backend/src/services/deletion/execute.py`'s core: `execute_deletion(db, deletion_request) -> None`, dispatching to a per-`target_type` ordered delete function (`_delete_learner`, `_delete_guardian`, `_delete_instructor`) built from data-model.md's cascade-order tables, wrapped in one transaction per target (commit sets `completed_at`; any exception rolls back the entire transaction -- zero partial deletes -- and leaves `completed_at` `NULL` so the request remains pending for the next run) (depends on T002, data-model.md)
- [ ] T006 [P] Implement `_delete_learner(db, target_learner_id)` in `backend/src/services/deletion/execute.py`: deletes, in data-model.md's learner-cascade order, `tutor_exchanges` → `tutoring_sessions` → `quiz_assignment_targets` → `assessment_events` → `generated_questions` where `learner_id = target_learner_id` (owned) → `SET NULL` on `generated_questions.flagged_by` where `flagged_by = target_learner_id AND generated_questions.learner_id != target_learner_id` (i.e. questions owned by a *different*, still-existing learner) → `mastery_states` → `enrollment_requests` → `enrollments` → `grade_progress` → `quiz_sessions` → `learner_profiles` → the learner's own `retention_records` row; then checks whether the learner's (now-former) `guardian_id` has zero remaining linked learners and, if so, calls `_delete_guardian` for that guardian (depends on T005)
- [ ] T007 [P] Implement `_delete_guardian(db, guardian_id)` in `backend/src/services/deletion/execute.py`: calls `_delete_learner` once per `learner_profiles.guardian_id = guardian_id` row, then deletes the `real_guardian_accounts` row itself (research.md R4) (depends on T005, T006)
- [ ] T008 [P] Implement `_delete_instructor(db, instructor_id)` in `backend/src/services/deletion/execute.py`: deletes `quiz_assignment_targets`/`quiz_assignments` scoped to the instructor's remaining (non-transferred) `classroom_rosters`, then those rosters (and their `enrollments`/`enrollment_requests`, roster-scoped only -- never the learner's own account, FR-008), then the `real_instructor_accounts` row, then its `retention_records` row (depends on T005)
- [ ] T009 [P] Implement `backend/src/services/deletion/inactivity.py`'s `sweep_inactive_accounts(db) -> int`: for every `RetentionRecord` with `enrollment_status = "inactive"` and `became_inactive_at` older than 1 year that has no existing pending `DeletionRequest` for its `(account_type, account_id)`, creates one with `requested_by = "system:inactivity-sweep"`; returns the count created (FR-005, research.md R8) (depends on T002)
- [ ] T010 [P] Unit tests for the cascade order in `backend/tests/unit/test_deletion_execute_ordering.py`: given a learner with rows in every cascade table, `_delete_learner` removes them in an order that never violates a still-existing FK (i.e. no `IntegrityError`) against a real (test) DB transaction; a `flagged_by` row pointing at the deleted learner but owned by a different, still-existing learner is `SET NULL`, not deleted (depends on T006)
- [ ] T011 [P] Unit test for transactional atomicity in `backend/tests/unit/test_deletion_execute_atomicity.py`: force a failure partway through `_delete_learner` (e.g. mock one of the later delete calls, such as `learner_profiles`, to raise) and assert (a) the whole transaction rolled back -- every row from earlier steps in the cascade, e.g. `mastery_states`/`assessment_events`, is still present, not partially deleted -- and (b) the `DeletionRequest.completed_at` stays `NULL` (FR-003; depends on T005, T006)

**Checkpoint**: Foundation ready -- user story implementation can now begin.

---

## Phase 3: User Story 1 - Guardian requests deletion of their learner's account (Priority: P1) 🎯 MVP

**Goal**: A guardian, instructor, or (via the instructor path, research.md
R6) institution can submit a deletion request against a learner,
guardian, or instructor account, and within the 30-day SLA every row
referencing that identity is hard-deleted with zero dangling references
left behind.

**Independent Test**: Seed a synthetic learner with mastery state,
assessment events, generated questions, and roster membership; submit a
deletion request on their behalf; run the cron executor; confirm every
row is gone and no other learner's or instructor's data was touched
(quickstart.md Scenario 1).

### Tests for User Story 1

- [ ] T012 [P] [US1] Contract tests for `POST /api/deletion-requests` in `backend/tests/contract/test_deletion_requests_api.py`: `201` + correct body shape for an authorized guardian→learner request and an authorized instructor→self request; `403` for an unauthorized target; `404` for a nonexistent `target_id`; `409` with `deletion_request_id` when a pending request already exists for the same target; `403` when the target has `is_demo = true` (contracts/api.md, FR-001, FR-006, FR-007)
- [ ] T013 [P] [US1] Contract tests for `GET /api/deletion-requests/{id}` in `backend/tests/contract/test_deletion_requests_api.py`: `200` with `status: "pending"` before processing; `403` for a caller who is not the original `requested_by`, whether the id exists or not (no-enumeration) (contracts/api.md, FR-009)
- [ ] T014 [P] [US1] Contract tests for `GET /api/cron/execute-deletions` in `backend/tests/integration/test_cron_execute_deletions_auth.py`: `503` when `CRON_SECRET` unset, `401` with wrong/missing bearer token, `200` with valid secret -- mirrors the existing `test_cron_classify_misconceptions_auth.py` pattern exactly (contracts/api.md)
- [ ] T015 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_cascade_learner.py`: seed a learner with rows in every table from data-model.md's learner cascade (mastery, assessment events, generated questions, enrollment, quiz session, tutoring session/exchange); submit + execute a deletion request; assert every one of those rows is gone and a sibling learner's data (same guardian, or same roster) is untouched (Acceptance Scenarios 1-2, SC-001). Also: (a) after completion, call `GET /api/learners/{id}/recommendations`, the mastery/dashboard endpoint, the roster list, and the instructor content-review queue for the deleted learner id and assert each returns a clean empty/404 result, never a 500 or a partial record (Acceptance Scenario 2's named read paths); (b) assert the `DeletionRequest` row itself still exists with `completed_at` set after the cascade completes -- it is the one row this feature never deletes (FR-010)
- [ ] T016 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_cascade_instructor.py`: instructor deletion with `transfer_rosters_to` reassigns the roster's `instructor_id` and leaves every enrolled learner's data intact; instructor deletion without a successor deletes the roster (and its roster-scoped `quiz_assignments`/`quiz_assignment_targets`) without deleting any enrolled learner (Acceptance Scenario 3, FR-008, SC-004)
- [ ] T017 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_already_completed_target.py`: submitting a request against an already-deleted/nonexistent target returns `404`; a request whose target was deleted by a concurrent path before the cron executor reaches it is marked completed without error, not retried forever (Acceptance Scenario 4, spec.md Edge Cases, SC-003)
- [ ] T018 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_demo_account_guard.py`: submission-time rejection of a demo-account target (`is_demo = true`) at `POST /api/deletion-requests`, and a defense-in-depth check that the cron executor itself also refuses to process a `DeletionRequest` whose target somehow has `is_demo = true` (FR-007, research.md R7)

### Implementation for User Story 1

- [ ] T019 [US1] Implement `POST /api/deletion-requests` in new `backend/src/api/routes/deletion.py`: resolves the caller via `current_session_claims`, validates the target exists and is not `is_demo`, calls `can_request_deletion()` (T003), checks for an existing pending request for the same `(target_type, target_id)` (raise `DeletionAlreadyPendingError` if found), and -- only for `target_type == "instructor"` with `transfer_rosters_to` present -- reassigns `classroom_rosters.instructor_id` synchronously before creating the `DeletionRequest` row (research.md R5) (depends on T001, T003)
- [ ] T020 [US1] Implement `GET /api/deletion-requests/{deletion_request_id}` in `backend/src/api/routes/deletion.py`: `404`/`403` via existing `NotFoundError`/`ForbiddenError` when the id doesn't exist or `requested_by` doesn't match the caller; otherwise returns `status` derived from `completed_at IS NULL` (depends on T019)
- [ ] T021 [US1] Add `GET /api/cron/execute-deletions` to `backend/src/api/routes/cron.py`, mirroring `classify_misconceptions_route`'s `_require_cron_secret` pattern exactly: calls `sweep_inactive_accounts()` (T009) then processes up to `MAX_DELETIONS_PER_RUN` pending `DeletionRequest` rows oldest-`requested_at`-first via `execute_deletion()` (T005), returning `{"status": "ok", "swept_count": ..., "processed_count": ..., "remaining_pending_count": ...}` (depends on T005, T009)
- [ ] T022 [US1] Add `MAX_DELETIONS_PER_RUN` (default `20`, env-overridable via `DELETION_MAX_PER_RUN`) constant in `backend/src/services/deletion/execute.py`, mirroring `classify.py`'s `MAX_PAIRS_PER_RUN`/`MISCONCEPTION_MAX_PAIRS_PER_RUN` pattern (research.md R1, tech-stack.md's cron batch size cap precedent) (depends on T005)
- [ ] T023 [US1] Add `/api/cron/execute-deletions` to `vercel.json`'s `crons` array with a daily schedule (e.g. `"0 8 * * *"`, after the existing `reset-demo-data`/`classify-misconceptions` entries) (depends on T021)

**Checkpoint**: User Story 1 is fully functional and independently
testable -- the core Principle VIII compliance gap is closed: a
submitted deletion request results in a real, verifiable hard delete.

---

## Phase 4: User Story 2 - Automatic deletion after a year of inactivity (Priority: P2)

**Goal**: An account inactive for more than a year is hard-deleted
through the exact same mechanism as an explicit request, with no
separate code path that could drift out of sync.

**Independent Test**: Seed a `RetentionRecord` with `became_inactive_at`
more than a year in the past, run the cron executor, and confirm the
linked account is deleted through the same cascade as a manual request
(quickstart.md Scenario 2).

### Tests for User Story 2

- [ ] T024 [P] [US2] Integration test in new `backend/tests/integration/test_deletion_inactivity_sweep.py`: a `RetentionRecord` inactive for >1 year with no existing pending request gets a `DeletionRequest` created (`requested_by = "system:inactivity-sweep"`) on the sweep phase, then deleted on the same or a subsequent run via the identical cascade User Story 1 already exercises (Acceptance Scenario 1, FR-005, SC-002)
- [ ] T025 [P] [US2] Integration test in new `backend/tests/integration/test_deletion_inactivity_threshold.py`: a `RetentionRecord` inactive for less than a year is left untouched by the sweep; a `RetentionRecord` whose `enrollment_status` returns to `"active"` before the 1-year mark is also left untouched, even if `became_inactive_at` is still set from a prior inactive period (Acceptance Scenarios 2-3)
- [ ] T026 [P] [US2] Integration test in new `backend/tests/integration/test_deletion_inactivity_no_duplicate.py`: running the sweep twice against the same overdue `RetentionRecord` creates only one `DeletionRequest`, never a duplicate (idempotent sweep)

### Implementation for User Story 2

- [ ] T027 [US2] Verify/extend `sweep_inactive_accounts()` (T009) to correctly join `RetentionRecord.account_type` (`learner`/`instructor` only, per data-model.md's note that guardians have no `RetentionRecord`) to the right target table when creating the `DeletionRequest`'s `target_type` (depends on T009, T024)

**Checkpoint**: User Stories 1 and 2 both work independently -- explicit
requests and inactivity-triggered deletions both flow through the one
cascade mechanism.

---

## Phase 5: User Story 3 - Guardian or instructor confirms a deletion request was honored (Priority: P3)

**Goal**: The original requester can check whether a submitted deletion
request has completed, without the response ever exposing any of the
target's own data.

**Independent Test**: Submit a deletion request, check its status before
and after the cron executor processes it, and confirm the status
reflects reality at each point (quickstart.md Scenario 3).

### Tests for User Story 3

- [ ] T028 [P] [US3] Integration test in new `backend/tests/integration/test_deletion_status_check.py`: `GET /api/deletion-requests/{id}` returns `status: "pending"`, `completed_at: null` before the cron run, and `status: "completed"` with a real `completed_at` timestamp after -- and asserts the response body contains no key beyond `deletion_request_id`/`target_type`/`status`/`requested_at`/`completed_at` (i.e. never the target's own fields) (Acceptance Scenarios 1-2, SC-005)

### Implementation for User Story 3

- [ ] T029 [US3] Confirm `GET /api/deletion-requests/{deletion_request_id}` (T020) already satisfies T028 as written; add the explicit response-shape allowlist assertion if the existing implementation returns anything broader (depends on T020, T028)

**Checkpoint**: All user stories independently functional. Full
compliance gate: explicit requests, inactivity-triggered deletions, and
requester-facing status confirmation all work end to end.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T030 [P] Run this repo's Constitution Principle III extensibility check (`check_no_subject_conditionals.py` or equivalent) against every file touched above -- confirm it stays clean (this feature has no subject-id-keyed logic at all, so this should trivially pass, but the check itself must still run per this repo's convention)
- [ ] T031 [P] Add a schema-introspection check (new script, e.g. `backend/scripts/check_deletion_cascade_coverage.py`), run in CI alongside T030: walks every FK constraint in the DB referencing `learner_profiles`, `real_guardian_accounts`, or `real_instructor_accounts`, and asserts each referencing table is either handled by `execute.py`'s cascade functions (T006-T008) or on an explicit, documented allowlist (e.g. `grading_response_cache`, per data-model.md's "Explicitly out of cascade scope"). Future-proofs SC-001 against a later milestone adding a new learner/guardian/instructor-linked table without updating the cascade
- [ ] T032 Run `quickstart.md` Scenarios 1-3 plus its two regression checks end to end against a real dev database
- [ ] T033 Run the full backend (`pytest`) suite -- confirm Milestones 1-17 pass unmodified (SC-001-005 regression). Per this project's convention, only the touched test files were run per phase above; this is the one full, unfiltered run
- [ ] T034 Update `specs/009-privacy-retention/data-classification.md`'s two "not yet implemented" cascade rows (mastery/assessment/questions, and Milestone 9's tutoring transcripts) to state the mechanism is now implemented, pointing at this feature instead of at the standing gap
- [ ] T035 Update `roadmap.md`'s Milestone 18 status line once implementation lands, with a full Definition of Done recorded against spec.md's SC-001-005 and this feature's actual test results (this repo's roadmap-status-line discipline)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Nothing to do -- proceed straight to Foundational.
- **Foundational (Phase 2)**: BLOCKS all user stories -- the cascade
  executor, authorization rules, and new error type must exist first,
  since every story's endpoints call into them.
- **User Stories (Phase 3-5)**: All depend on Foundational. US1 is the
  MVP and delivers the entire Principle VIII compliance gate on its own.
  US2 depends on US1's `execute_deletion()` (T005) existing -- it only
  adds the code path that *creates* requests automatically, reusing the
  same executor. US3 depends on US1's status endpoint (T020) already
  existing -- it adds no new endpoint, only confirms/hardens the
  existing one's response shape.
- **Polish (Phase 6)**: Depends on all three user stories being
  complete.

### Within Each User Story

- Tests written first, confirmed to fail before implementation.
- Authorization + cascade executor (Foundational) before the endpoints
  that call them (User Story 1) before the automatic-trigger path (User
  Story 2) before the status-confirmation hardening (User Story 3).

### Parallel Opportunities

- T001-T002 (new error type, package init) in parallel.
- T006-T009 (per-target-type cascade functions and the inactivity
  sweep, different functions in largely independent code paths) once
  T005's dispatch skeleton exists.
- T012-T018 (all US1 tests, different files) once Foundational is done.
- T024-T026 (all US2 tests) can be written alongside US1 implementation
  once Foundational is done, since they target different files.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "Contract tests for POST/GET /api/deletion-requests in backend/tests/contract/test_deletion_requests_api.py"
Task: "Contract tests for GET /api/cron/execute-deletions auth in backend/tests/integration/test_cron_execute_deletions_auth.py"
Task: "Integration test for learner cascade + post-deletion read paths in backend/tests/integration/test_deletion_cascade_learner.py"
Task: "Integration test for instructor cascade/roster transfer in backend/tests/integration/test_deletion_cascade_instructor.py"
Task: "Integration test for already-deleted target handling in backend/tests/integration/test_deletion_already_completed_target.py"
Task: "Integration test for demo-account guard in backend/tests/integration/test_deletion_demo_account_guard.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (authorization rules + cascade
   executor + inactivity-sweep skeleton, even though US2 wires the
   sweep's trigger path in later).
2. Complete Phase 3: User Story 1.
3. **STOP and VALIDATE**: run quickstart.md Scenario 1 and its two
   regression checks against a real dev database.
4. Deploy/demo if ready -- this alone closes the standing Constitution
   Principle VIII gap (roadmap.md's former "Known gap" entry).

### Incremental Delivery

1. Foundational -> US1 (MVP: explicit deletion requests actually
   execute) -> US2 (inactivity-triggered deletion reuses the same
   mechanism) -> US3 (status-check hardening) -> Polish.
2. Each story adds value without breaking the previous one -- US2 and
   US3 touch different concerns (automatic triggering vs. requester
   visibility) and don't require re-testing US1's core cascade.
