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

No new project, service, or dependency (plan.md's Structure Decision).
One schema change (one new nullable column on `RetentionRecord`,
FR-011) is handled in Foundational below, per this repo's convention of
putting schema/migration work there rather than in Setup. Nothing else
to do here.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared plumbing every user story's endpoints and cron
logic depend on -- error type, authorization rules, the schema change,
and the cascade executor's dependency-order table walk itself.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T001 [P] Add `DeletionAlreadyPendingError` (409, carries `deletion_request_id`) to `backend/src/api/errors.py`, and its handler in `backend/src/api/main.py` returning `{"error": "deletion_already_pending", "deletion_request_id": str(exc.deletion_request_id)}` (contracts/api.md)
- [X] T002 [P] Create `backend/src/services/deletion/__init__.py` (empty package init)
- [X] T003 [US1][US2] Implement `backend/src/services/deletion/authorization.py`: `can_request_deletion(requester_claims, target_type, target_id, db) -> bool` per contracts/api.md's authorization table (guardian → self or own linked learner; instructor → self or a learner enrolled in one of their rosters) (depends on T002)
- [X] T004 [P] Unit tests for `authorization.py` in `backend/tests/unit/test_deletion_authorization.py`: guardian may target self and their own linked learner; guardian may NOT target an unrelated learner or an instructor; instructor may target self and a learner in one of their rosters; instructor may NOT target a learner outside every roster they own (depends on T003)
- [X] T005 [P] Add `inactivity_warning_sent_at: Mapped[datetime | None]` (nullable `DateTime`) to `RetentionRecord` in `backend/src/models/retention_record.py` (FR-011, data-model.md)
- [X] T006 Alembic migration in `backend/alembic/versions/<rev>_deletion_pathway_warning_column.py`: `ALTER TABLE retention_records ADD COLUMN inactivity_warning_sent_at TIMESTAMPTZ NULL` -- additive-only, no backfill needed (data-model.md's Migration section) (depends on T005)
- [X] T007 Implement `backend/src/services/deletion/execute.py`'s core: `execute_deletion(db, deletion_request) -> None`, dispatching to a per-`target_type` ordered delete function (`_delete_learner`, `_delete_guardian`, `_delete_instructor`) built from data-model.md's cascade-order tables, wrapped in one transaction per target (commit sets `completed_at`; any exception rolls back the entire transaction -- zero partial deletes -- and leaves `completed_at` `NULL` so the request remains pending for the next run) (depends on T002, data-model.md)
- [X] T008 [P] Implement `_delete_learner(db, target_learner_id)` in `backend/src/services/deletion/execute.py`: deletes, in data-model.md's learner-cascade order, `tutor_exchanges` → `tutoring_sessions` → `quiz_assignment_targets` → `assessment_events` → `generated_questions` where `learner_id = target_learner_id` (owned) → `SET NULL` on `generated_questions.flagged_by` where `flagged_by = target_learner_id AND generated_questions.learner_id != target_learner_id` (i.e. questions owned by a *different*, still-existing learner) → `mastery_states` → `enrollment_requests` → `enrollments` → `grade_progress` → `quiz_sessions` → `learner_profiles` → the learner's own `retention_records` row; then checks whether the learner's (now-former) `guardian_id` has zero remaining linked learners and, if so, calls `_delete_guardian` for that guardian (depends on T007)
- [X] T009 [P] Implement `_delete_guardian(db, guardian_id)` in `backend/src/services/deletion/execute.py`: calls `_delete_learner` once per `learner_profiles.guardian_id = guardian_id` row, then deletes the `real_guardian_accounts` row itself (research.md R4) (depends on T007, T008)
- [X] T010 [P] Implement `_delete_instructor(db, instructor_id)` in `backend/src/services/deletion/execute.py`: deletes `quiz_assignment_targets`/`quiz_assignments` scoped by `roster_id` to the instructor's remaining (non-transferred) `classroom_rosters` only -- never scoped by `instructor_id` directly, since a transferred roster's assignments must survive (data-model.md) -- then those rosters (and their `enrollments`/`enrollment_requests`, roster-scoped only -- never the learner's own account, FR-008), then the `real_instructor_accounts` row, then its `retention_records` row (depends on T007)
- [X] T011 [P] Implement `backend/src/services/deletion/inactivity.py`'s `sweep_inactive_accounts(db) -> int`: for every `RetentionRecord` with `enrollment_status = "inactive"` and `became_inactive_at` older than 1 year that has no existing pending `DeletionRequest` for its `(account_type, account_id)`, creates one with `requested_by = "system:inactivity-sweep"`; returns the count created (FR-005, research.md R8) (depends on T002)
- [X] T012 [P] Implement `backend/src/services/deletion/inactivity.py`'s `reconcile_inactivity_warnings(db) -> int`: for every `RetentionRecord`, apply two mutually exclusive, ordered checks (research.md R10) -- **(1)** if `enrollment_status = "active"` and `inactivity_warning_sent_at` is not `NULL`, clear it to `NULL` (checked first, regardless of `became_inactive_at`); **(2)** else, if `enrollment_status = "inactive"` and `inactivity_warning_sent_at` is `NULL` and inactivity age crosses `became_inactive_at + (1 year - 7 days)`, set `inactivity_warning_sent_at = now()`. The `enrollment_status = "inactive"` guard on (2) is required, not incidental -- a stale, pre-reactivation `became_inactive_at` must never re-trigger a warning on an active account. Returns the count of records whose warning state changed this run (FR-011) (depends on T006)
- [X] T013 [P] Unit tests for the cascade order in `backend/tests/unit/test_deletion_execute_ordering.py`: given a learner with rows in every cascade table, `_delete_learner` removes them in an order that never violates a still-existing FK (i.e. no `IntegrityError`) against a real (test) DB transaction; a `flagged_by` row pointing at the deleted learner but owned by a different, still-existing learner is `SET NULL`, not deleted (depends on T008)
- [X] T014 [P] Unit test for transactional atomicity in `backend/tests/unit/test_deletion_execute_atomicity.py`: force a failure partway through `_delete_learner` (e.g. mock one of the later delete calls, such as `learner_profiles`, to raise) and assert (a) the whole transaction rolled back -- every row from earlier steps in the cascade, e.g. `mastery_states`/`assessment_events`, is still present, not partially deleted -- and (b) the `DeletionRequest.completed_at` stays `NULL` (FR-003; depends on T007, T008)
- [X] T015 [P] Unit tests for `reconcile_inactivity_warnings` in `backend/tests/unit/test_deletion_inactivity_warnings.py`: a record crossing the 7-day-out threshold gets `inactivity_warning_sent_at` set exactly once (a second run with no state change doesn't overwrite the timestamp); a record already past the threshold with the field already set is left untouched; a record with `enrollment_status = "active"` and a stale non-null `inactivity_warning_sent_at` gets it cleared to `NULL`; an `enrollment_status = "active"` record with a stale non-null `became_inactive_at` that would otherwise satisfy the threshold arithmetic is NOT (re-)warned -- the active-status guard on the set branch takes precedence (depends on T012)

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

- [X] T016 [P] [US1] Contract tests for `POST /api/deletion-requests` in `backend/tests/contract/test_deletion_requests_api.py`: `201` + correct body shape for an authorized guardian→learner request and an authorized instructor→self request; `403` for an unauthorized target; `404` for a nonexistent `target_id`; `409` with `deletion_request_id` when a pending request already exists for the same target; `403` when the target has `is_demo = true` (contracts/api.md, FR-001, FR-006, FR-007)
- [X] T017 [P] [US1] Contract tests for `GET /api/deletion-requests/{id}` in `backend/tests/contract/test_deletion_requests_api.py`: `200` with `status: "pending"` before processing; `403` for a caller who is not the original `requested_by`, whether the id exists or not (no-enumeration) (contracts/api.md, FR-009)
- [X] T018 [P] [US1] Contract tests for `GET /api/cron/execute-deletions` in `backend/tests/integration/test_cron_execute_deletions_auth.py`: `503` when `CRON_SECRET` unset, `401` with wrong/missing bearer token, `200` with valid secret -- mirrors the existing `test_cron_classify_misconceptions_auth.py` pattern exactly (contracts/api.md)
- [X] T019 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_cascade_learner.py`: seed a learner with rows in every table from data-model.md's learner cascade (mastery, assessment events, generated questions, enrollment, quiz session, tutoring session/exchange); submit + execute a deletion request; assert every one of those rows is gone and a sibling learner's data (same guardian, or same roster) is untouched (Acceptance Scenarios 1-2, SC-001). Also: (a) after completion, call `GET /api/learners/{id}/recommendations`, the mastery/dashboard endpoint, the roster list, and the instructor content-review queue for the deleted learner id and assert each returns a clean empty/404 result, never a 500 or a partial record (Acceptance Scenario 2's named read paths); (b) assert the `DeletionRequest` row itself still exists with `completed_at` set after the cascade completes -- it is the one row this feature never deletes (FR-010)
- [X] T020 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_cascade_instructor.py`: instructor deletion with `transfer_rosters_to` reassigns the roster's `instructor_id` and leaves every enrolled learner's data intact; instructor deletion without a successor deletes the roster (and its roster-scoped `quiz_assignments`/`quiz_assignment_targets`) without deleting any enrolled learner (Acceptance Scenario 3, FR-008, SC-004)
- [X] T021 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_already_completed_target.py`: submitting a request against an already-deleted/nonexistent target returns `404`; a request whose target was deleted by a concurrent path before the cron executor reaches it is marked completed without error, not retried forever (Acceptance Scenario 4, spec.md Edge Cases, SC-003)
- [X] T022 [P] [US1] Integration test in new `backend/tests/integration/test_deletion_demo_account_guard.py`: submission-time rejection of a demo-account target (`is_demo = true`) at `POST /api/deletion-requests`, and a defense-in-depth check that the cron executor itself also refuses to process a `DeletionRequest` whose target somehow has `is_demo = true` (FR-007, research.md R7)

### Implementation for User Story 1

- [X] T023 [US1] Implement `POST /api/deletion-requests` in new `backend/src/api/routes/deletion.py`: resolves the caller via `current_session_claims`, validates the target exists and is not `is_demo`, calls `can_request_deletion()` (T003), checks for an existing pending request for the same `(target_type, target_id)` (raise `DeletionAlreadyPendingError` if found), and -- only for `target_type == "instructor"` with `transfer_rosters_to` present -- reassigns *both* `classroom_rosters.instructor_id` and `quiz_assignments.instructor_id` (for every assignment on that roster) to the successor synchronously before creating the `DeletionRequest` row (data-model.md step 1, research.md R5) (depends on T001, T003)
- [X] T024 [US1] Implement `GET /api/deletion-requests/{deletion_request_id}` in `backend/src/api/routes/deletion.py`: `404`/`403` via existing `NotFoundError`/`ForbiddenError` when the id doesn't exist or `requested_by` doesn't match the caller; otherwise returns `status` derived from `completed_at IS NULL` (depends on T023)
- [X] T025 [US1] Add `GET /api/cron/execute-deletions` to `backend/src/api/routes/cron.py`, mirroring `classify_misconceptions_route`'s `_require_cron_secret` pattern exactly: calls `reconcile_inactivity_warnings()` (T012) then `sweep_inactive_accounts()` (T011) then processes up to `MAX_DELETIONS_PER_RUN` pending `DeletionRequest` rows oldest-`requested_at`-first via `execute_deletion()` (T007), returning `{"status": "ok", "swept_count": ..., "processed_count": ..., "remaining_pending_count": ...}` (depends on T007, T011, T012)
- [X] T026 [US1] Add `MAX_DELETIONS_PER_RUN` (default `20`, env-overridable via `DELETION_MAX_PER_RUN`) constant in `backend/src/services/deletion/execute.py`, mirroring `classify.py`'s `MAX_PAIRS_PER_RUN`/`MISCONCEPTION_MAX_PAIRS_PER_RUN` pattern (research.md R1, tech-stack.md's cron batch size cap precedent) (depends on T007)
- [X] T027 [US1] Add `/api/cron/execute-deletions` to `vercel.json`'s `crons` array with a daily schedule (e.g. `"0 8 * * *"`, after the existing `reset-demo-data`/`classify-misconceptions` entries) (depends on T025)

**Checkpoint**: User Story 1 is fully functional and independently
testable -- the core Principle VIII compliance gap is closed: a
submitted deletion request results in a real, verifiable hard delete.

---

## Phase 4: User Story 2 - Automatic deletion after a year of inactivity (Priority: P2)

**Goal**: An account inactive for more than a year is hard-deleted
through the exact same mechanism as an explicit request, with no
separate code path that could drift out of sync -- and the owning
guardian/instructor sees an in-app warning at least 7 days before that
deletion happens (FR-011).

**Independent Test**: Seed a `RetentionRecord` with `became_inactive_at`
more than a year in the past, run the cron executor, and confirm the
linked account is deleted through the same cascade as a manual request
(quickstart.md Scenario 2). Separately, seed one 7 days short of the
one-year mark and confirm the warning appears via `whoami` before any
deletion occurs (quickstart.md Scenario 2b).

### Tests for User Story 2

- [ ] T028 [P] [US2] Integration test in new `backend/tests/integration/test_deletion_inactivity_sweep.py`: a `RetentionRecord` inactive for >1 year with no existing pending request gets a `DeletionRequest` created (`requested_by = "system:inactivity-sweep"`) on the sweep phase, then deleted on the same or a subsequent run via the identical cascade User Story 1 already exercises (Acceptance Scenario 1, FR-005, SC-002)
- [ ] T029 [P] [US2] Integration test in new `backend/tests/integration/test_deletion_inactivity_threshold.py`: a `RetentionRecord` inactive for less than a year is left untouched by the sweep; a `RetentionRecord` whose `enrollment_status` returns to `"active"` before the 1-year mark is also left untouched, even if `became_inactive_at` is still set from a prior inactive period (Acceptance Scenarios 2-3)
- [ ] T030 [P] [US2] Integration test in new `backend/tests/integration/test_deletion_inactivity_no_duplicate.py`: running the sweep twice against the same overdue `RetentionRecord` creates only one `DeletionRequest`, never a duplicate (idempotent sweep)
- [ ] T031 [P] [US2] Integration test in new `backend/tests/integration/test_deletion_inactivity_warning.py`: a `RetentionRecord` 7 days short of the one-year mark causes `GET /api/auth/whoami` (called with the owning guardian's/instructor's session) to include a `pending_deletion_warnings` entry with the correct `scheduled_deletion_date`; no `DeletionRequest` exists yet at that point; reactivating the record (`enrollment_status = "active"`) and re-running the cron makes the entry disappear from `whoami` on the next call (Acceptance Scenario 4, FR-011, SC-006, quickstart.md Scenario 2b). Also, on a separate seeded record: confirm the warning does NOT block deletion -- advance the same warned record's `became_inactive_at` past the full one-year mark, re-run the cron, and assert it proceeds to a normal pending-then-completed `DeletionRequest` exactly like any other overdue account (spec.md Edge Cases: "the warning is informational only and never blocks or delays FR-005's deletion")
- [ ] T032 [P] [US2] Vitest test for the warning banner in new `frontend/tests/unit/nav-deletion-warning.test.tsx`: `Nav` renders a visible warning banner naming the scheduled deletion date when `whoami`'s `pending_deletion_warnings` is non-empty; renders nothing extra when the list is empty (the common case)

### Implementation for User Story 2

- [ ] T033 [US2] Verify/extend `sweep_inactive_accounts()` (T011) to correctly join `RetentionRecord.account_type` (`learner`/`instructor` only, per data-model.md's note that guardians have no `RetentionRecord`) to the right target table when creating the `DeletionRequest`'s `target_type` (depends on T011, T028)
- [ ] T034 [US2] Extend `WhoAmIOut`/`whoami()` in `backend/src/api/routes/auth.py` to add `pending_deletion_warnings` (contracts/api.md): for a guardian session, one entry per `learner_profiles.guardian_id = guardian.guardian_id` row joined to its `RetentionRecord` via the direct FK (`learner_profiles.retention_record_id = retention_records.retention_record_id` -- not the soft `account_type`/`account_id` match T011/T033's sweep uses, since this join has an actual enforced foreign key available) whose `inactivity_warning_sent_at` is not `NULL`; for an instructor session, at most one entry for the instructor's own `RetentionRecord` (looked up via `account_type = 'instructor' AND account_id = instructor.instructor_id`, the only option there since `RealInstructorAccount` has no direct FK to `RetentionRecord`); empty list otherwise (including every demo session type) (research.md R9; depends on T005, T012)
- [ ] T035 [US2] Extend `WhoAmIResponse` in `frontend/src/services/api.ts` with the new optional `pending_deletion_warnings` field, matching contracts/api.md's shape (depends on T034)
- [ ] T036 [US2] Extend `frontend/src/components/Nav.tsx` to render a warning banner (target type, scheduled deletion date) for each entry in `pending_deletion_warnings` when the list is non-empty (depends on T035, T032)

**Checkpoint**: User Stories 1 and 2 both work independently -- explicit
requests and inactivity-triggered deletions both flow through the one
cascade mechanism, and nobody's account disappears without at least 7
days' visible warning.

---

## Phase 5: User Story 3 - Guardian or instructor confirms a deletion request was honored (Priority: P3)

**Goal**: The original requester can check whether a submitted deletion
request has completed, without the response ever exposing any of the
target's own data.

**Independent Test**: Submit a deletion request, check its status before
and after the cron executor processes it, and confirm the status
reflects reality at each point (quickstart.md Scenario 3).

### Tests for User Story 3

- [ ] T037 [P] [US3] Integration test in new `backend/tests/integration/test_deletion_status_check.py`: `GET /api/deletion-requests/{id}` returns `status: "pending"`, `completed_at: null` before the cron run, and `status: "completed"` with a real `completed_at` timestamp after -- and asserts the response body contains no key beyond `deletion_request_id`/`target_type`/`status`/`requested_at`/`completed_at` (i.e. never the target's own fields) (Acceptance Scenarios 1-2, SC-005)

### Implementation for User Story 3

- [ ] T038 [US3] Confirm `GET /api/deletion-requests/{deletion_request_id}` (T024) already satisfies T037 as written; add the explicit response-shape allowlist assertion if the existing implementation returns anything broader (depends on T024, T037)

**Checkpoint**: All user stories independently functional. Full
compliance gate: explicit requests, inactivity-triggered deletions,
pre-deletion warning, and requester-facing status confirmation all work
end to end.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T039 [P] Run this repo's Constitution Principle III extensibility check (`check_no_subject_conditionals.py` or equivalent) against every file touched above -- confirm it stays clean (this feature has no subject-id-keyed logic at all, so this should trivially pass, but the check itself must still run per this repo's convention)
- [ ] T040 [P] Add a schema-introspection check (new script, e.g. `backend/scripts/check_deletion_cascade_coverage.py`), run in CI alongside T039: walks every FK constraint in the DB referencing `learner_profiles`, `real_guardian_accounts`, or `real_instructor_accounts`, and asserts each referencing table is either handled by `execute.py`'s cascade functions (T008-T010) or on an explicit, documented allowlist (e.g. `grading_response_cache`, per data-model.md's "Explicitly out of cascade scope"). Future-proofs SC-001 against a later milestone adding a new learner/guardian/instructor-linked table without updating the cascade
- [ ] T041 Run `quickstart.md` Scenarios 1-3 (including 2b) plus its two regression checks end to end against a real dev database
- [ ] T042 Run the full backend (`pytest`) and frontend (`npm test`) suites -- confirm Milestones 1-17 pass unmodified (SC-001-006 regression). Per this project's convention, only the touched test files were run per phase above; this is the one full, unfiltered run
- [ ] T043 Update `specs/009-privacy-retention/data-classification.md`'s two "not yet implemented" cascade rows (mastery/assessment/questions, and Milestone 9's tutoring transcripts) to state the mechanism is now implemented, pointing at this feature instead of at the standing gap
- [ ] T044 Update `roadmap.md`'s Milestone 18 status line once implementation lands, with a full Definition of Done recorded against spec.md's SC-001-006 and this feature's actual test results (this repo's roadmap-status-line discipline)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Nothing to do -- proceed straight to Foundational.
- **Foundational (Phase 2)**: BLOCKS all user stories -- the schema
  change, cascade executor, authorization rules, and new error type
  must exist first, since every story's endpoints call into them.
- **User Stories (Phase 3-5)**: All depend on Foundational. US1 is the
  MVP and delivers the entire Principle VIII compliance gate on its own.
  US2 depends on US1's `execute_deletion()` (T007) and the cron route
  (T025) already existing -- it adds the code path that *creates*
  requests automatically and the warning that precedes it, reusing the
  same executor and cron job. US3 depends on US1's status endpoint
  (T024) already existing -- it adds no new endpoint, only confirms/
  hardens the existing one's response shape.
- **Polish (Phase 6)**: Depends on all three user stories being
  complete.

### Within Each User Story

- Tests written first, confirmed to fail before implementation.
- Schema change + authorization + cascade executor (Foundational)
  before the endpoints that call them (User Story 1) before the
  automatic-trigger and warning path (User Story 2) before the
  status-confirmation hardening (User Story 3).

### Parallel Opportunities

- T001-T002 (new error type, package init) in parallel.
- T005 (model field) can start immediately; T006 (migration) follows it.
- T008-T012 (per-target-type cascade functions, the deletion sweep, and
  the warning reconciliation -- different functions in largely
  independent code paths) once T007's dispatch skeleton and T006's
  migration exist.
- T016-T022 (all US1 tests, different files) once Foundational is done.
- T028-T032 (all US2 tests, including the new frontend test) can be
  written alongside US1 implementation once Foundational is done, since
  they target different files.

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

1. Complete Phase 2: Foundational (schema change + authorization rules +
   cascade executor + inactivity-sweep/warning-reconciliation
   skeletons, even though US2 wires their trigger paths in later).
2. Complete Phase 3: User Story 1.
3. **STOP and VALIDATE**: run quickstart.md Scenario 1 and its two
   regression checks against a real dev database.
4. Deploy/demo if ready -- this alone closes the standing Constitution
   Principle VIII gap (roadmap.md's former "Known gap" entry).

### Incremental Delivery

1. Foundational -> US1 (MVP: explicit deletion requests actually
   execute) -> US2 (inactivity-triggered deletion and its pre-deletion
   warning both reuse the same mechanism/cron job) -> US3 (status-check
   hardening) -> Polish.
2. Each story adds value without breaking the previous one -- US2 and
   US3 touch different concerns (automatic triggering + warning vs.
   requester visibility) and don't require re-testing US1's core
   cascade.
