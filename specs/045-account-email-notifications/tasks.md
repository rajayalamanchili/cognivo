---

description: "Task list for Account Email Notifications"
---

# Tasks: Account Email Notifications

**Input**: Design documents from `/specs/045-account-email-notifications/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included -- `plan.md`'s own Project Structure names these test
files explicitly, and this codebase's existing convention (every prior
spec) is contract/integration/unit coverage per feature.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3,
priority order P1/P2/P3) so each can be implemented and tested
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an
  incomplete task)
- **[Story]**: US1/US2/US3, per spec.md
- File paths are exact, relative to the repository root

## Path Conventions

Web app (existing split, per plan.md's Structure Decision):
`backend/src/`, `backend/tests/`, `frontend/src/app/`.

---

## Phase 1: Setup

**Purpose**: New env vars and dependency reclassification, no code yet.

- [X] T001 [P] Add `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `FRONTEND_BASE_URL` (with research.md §1/§6 doc comments matching this file's existing style) to `backend/.env.example`
- [X] T002 [P] Move `httpx` from the `dev` dependency group to main `dependencies` in `backend/pyproject.toml` (research.md §1 -- no new package, just reclassified)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The notification-logging/sending infrastructure every user
story's trigger points call into. No user story can be implemented
until this phase is done.

**⚠️ CRITICAL**: Blocks all of Phase 3+.

- [X] T003 [P] Add `NotificationType` (`registration`/`password_reset`/`deletion_request_confirmation`) and `NotificationStatus` (`sent`/`failed`) enums to `backend/src/models/enums.py` (data-model.md)
- [X] T004 [P] Create `PasswordResetToken` model in `backend/src/models/password_reset_token.py` (data-model.md -- `AuthorizedByType` account_type, non-FK account_id, token_hash, created_at, expires_at, used_at)
- [X] T005 [P] Create `NotificationLogEntry` model in `backend/src/models/notification_log_entry.py` (data-model.md -- notification_type, account_type, non-FK account_id, attempted_at, status, error_detail)
- [X] T006 Create Alembic migration for both new tables, including the `uq_password_reset_tokens_pending_account` partial unique index on `(account_type, account_id) WHERE used_at IS NULL` (depends on T003, T004, T005) in `backend/alembic/versions/`
- [X] T007 Create `backend/src/services/notifications/mailer.py`: `send_email(to_email, subject, body) -> bool`, a single `httpx.post()` to Resend's `/emails` endpoint with a 10s timeout, catching every exception/non-2xx response as a failure, never raising (research.md §1/§5/§7; depends on T002)
- [X] T008 Create `backend/src/services/notifications/notify.py`: `notify_registration`, `notify_password_reset`, `notify_deletion_request` -- each takes a required `is_demo: bool` that short-circuits before any send/log (FR-011), calls `mailer.send_email`, and writes one `NotificationLogEntry` row (sent/failed) on the caller's `db` session (research.md §5; depends on T005, T006, T007)

**Checkpoint**: Foundation ready -- user stories can now proceed.

---

## Phase 3: User Story 1 - Password reset by email (Priority: P1) 🎯 MVP

**Goal**: A locked-out guardian or instructor requests a reset link by
email from their own sign-in page, follows it, sets a new password, and
is signed in.

**Independent Test**: Per spec.md's own Independent Test for US1 --
submit a reset request as a guardian (and separately an instructor) with
a known account email, retrieve the emailed link, set a new password,
confirm sign-in succeeds with the new password and fails with the old
one.

### Implementation for User Story 1

- [X] T009 [P] [US1] Create `backend/src/services/auth/reset_tokens.py`: issue (invalidate-prior + insert, with one retry on the partial-unique-index `IntegrityError`), hash (`secrets.token_urlsafe(32)` + SHA-256), verify (`used_at IS NULL AND expires_at > now()`), and the 60-second reset-request rate-limit check (research.md §2/§3; depends on T004, T006)
- [X] T010 [US1] Add `POST /api/auth/guardian/forgot-password` and `POST /api/auth/guardian/reset-password` to `backend/src/api/routes/auth.py` (contracts/api.md; depends on T008, T009)
- [X] T011 [US1] Add `POST /api/auth/instructor/forgot-password` and `POST /api/auth/instructor/reset-password` to `backend/src/api/routes/auth.py` (contracts/api.md; depends on T008, T009; same file as T010, sequential)
- [X] T012 [P] [US1] Unit tests for `reset_tokens.py` (hash/expiry/invalidation/rate-limit, concurrent-issue retry) in `backend/tests/unit/test_reset_tokens.py`
- [X] T013 [P] [US1] Integration tests for the guardian forgot/reset-password flow (happy path, reuse-rejected, expiry-rejected, no-enumeration on unknown/demo email) in `backend/tests/integration/test_auth_guardian_password_reset.py`
- [X] T014 [P] [US1] Integration tests for the instructor forgot/reset-password flow (same coverage as T013) in `backend/tests/integration/test_auth_instructor_password_reset.py`
- [X] T015 [P] [US1] Create guardian forgot-password page in `frontend/src/app/(auth)/guardian/forgot-password/page.tsx`
- [X] T016 [P] [US1] Create guardian reset-password page in `frontend/src/app/(auth)/guardian/reset-password/page.tsx`
- [X] T017 [P] [US1] Create instructor forgot-password page in `frontend/src/app/(auth)/instructor/forgot-password/page.tsx`
- [X] T018 [P] [US1] Create instructor reset-password page in `frontend/src/app/(auth)/instructor/reset-password/page.tsx`
- [X] T019 [P] [US1] Add a "Forgot password?" link for the guardian sign-in form (spec 041 since restructured `(auth)/guardian/sign-in/page.tsx` into a thin redirect to the unified `/sign-in?tab=guardian` page -- the actual form lives in the shared `frontend/src/components/AuthForm.tsx`, edited there instead so both roles get the link from one change)
- [X] T020 [P] [US1] Add a "Forgot password?" link for the instructor sign-in form (same `AuthForm.tsx` edit as T019 -- covers both tabs)

**Checkpoint**: User Story 1 is fully functional and independently
testable (quickstart.md Scenarios 1-2).

---

## Phase 4: User Story 2 - Registration confirmation (Priority: P2)

**Goal**: A new guardian or instructor receives a confirmation email
immediately after their real account is created.

**Independent Test**: Register a new real guardian account (and
separately a new real instructor account) and confirm a
confirmation email is sent; confirm a failed registration sends none.

### Implementation for User Story 2

- [X] T021 [US2] Call `notify_registration` from `register_guardian` in `backend/src/api/routes/auth.py`, after its existing commit (depends on T008; same file as T010/T011, sequential)
- [X] T022 [US2] Call `notify_registration` from `register_instructor` in `backend/src/api/routes/auth.py`, after its existing commit (depends on T008; same file, sequential)
- [X] T023 [P] [US2] Integration tests for registration-confirmation emails (guardian + instructor sent, failed/duplicate registration sends none, `notification_log_entries` row shape) in `backend/tests/integration/test_notifications_registration.py`

**Checkpoint**: User Stories 1 and 2 both independently functional
(quickstart.md Scenario 3).

---

## Phase 5: User Story 3 - Deletion-request confirmation (Priority: P3)

**Goal**: A guardian or instructor is notified by email when a
deletion request targeting their own account, or a learner they
manage, is accepted -- including when the request is system/
inactivity-generated.

**Independent Test**: Submit a self-account deletion request (and
separately a learner-data deletion request as that learner's guardian)
and confirm a confirmation email reaches the requester; confirm a
duplicate-pending rejection sends none; confirm an inactivity-swept
request also notifies.

### Implementation for User Story 3

- [X] T024 [US3] Call `notify_deletion_request` from `submit_deletion_request` in `backend/src/api/routes/deletion.py`, after its existing commit -- resolving the recipient to the managing guardian when `target_type == LEARNER` (research.md §5; depends on T008)
- [X] T025 [US3] Restructure `sweep_inactive_accounts` in `backend/src/services/deletion/inactivity.py` to commit each `DeletionRequest` individually and call `notify_deletion_request` right after, resolving the recipient from `RetentionRecord.account_type` (`LEARNER` -> managing guardian, `INSTRUCTOR` -> the instructor itself) (research.md §5; depends on T008). This changes the function's commit granularity from one batched `db.commit()` at the loop's end to one per record -- re-run the existing spec-020 suite (`test_deletion_inactivity_sweep.py`, `test_deletion_inactivity_no_duplicate.py`, `test_deletion_inactivity_threshold.py`) afterward and fix any assumption that depended on the old single-commit-at-end shape (/speckit-analyze finding I1)
- [X] T026 [P] [US3] Integration tests for deletion-request confirmation (self guardian/instructor, learner-target notifies the guardian not the learner, duplicate-pending sends none, system/inactivity-generated request also notifies) in `backend/tests/integration/test_notifications_deletion_request.py`
- [X] T027 [P] [US3] Integration test confirming zero `notification_log_entries` rows are ever written for a demo guardian/instructor/demo-learner's-guardian across all three trigger points in `backend/tests/integration/test_notifications_demo_guard.py`

**Checkpoint**: All three user stories independently functional
(quickstart.md Scenarios 4-5).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Run every `quickstart.md` scenario end to end against a local dev server with a real (or deliberately invalid) `RESEND_API_KEY`
- [X] T029 [P] Lint/format pass (`ruff`, `black`) across every new/edited backend file from this feature
- [X] T030 [P] Unit test: mock `mailer.send_email` to return `False`/raise for each of `notify_registration`, `notify_password_reset`, `notify_deletion_request`, and assert each still writes exactly one `NotificationLogEntry` row with `status=failed` and never raises (FR-012/FR-013) in `backend/tests/unit/test_notify_failure_handling.py`
- [X] T031 [P] Integration test: with `mailer.send_email` mocked to fail, confirm all three trigger-point HTTP actions -- `register_guardian`/`register_instructor`, `forgot-password` (guardian + instructor), and `submit_deletion_request` -- still return their normal success response (SC-006) in `backend/tests/integration/test_notifications_failure_resilience.py` (/speckit-analyze finding E1)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T002 needs `httpx`
  reclassified before T007 imports it). Blocks every user story.
- **User Stories (Phase 3-5)**: All depend on Foundational completion.
  US1, US2, and US3 touch `auth.py`/`deletion.py`/`inactivity.py` at
  different, non-overlapping call sites, so they're independently
  implementable even though US2/US3 share files with US1's own edits
  (sequence within a shared file, not a cross-story blocking
  dependency).
- **Polish (Phase 6)**: Depends on whichever stories are in scope for
  this delivery being complete. T031 specifically needs all three
  stories' wiring done (it asserts the failure-resilience property at
  every trigger point), so it is the one Polish task that can't start
  until US1+US2+US3 are all in.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3. The MVP on its own.
- **US2 (P2)**: No dependency on US1/US3 beyond the shared Foundational
  `notify.py`. Independently testable even if US1 isn't implemented yet.
- **US3 (P3)**: Same as US2 -- independent of US1/US2 beyond
  Foundational.

### Within Each User Story

- Service/helper modules before the routes that call them.
- Routes before their integration tests.
- Backend endpoints before the frontend pages that call them (US1).

### Parallel Opportunities

- T001/T002 (Setup) in parallel.
- T003/T004/T005 (Foundational models/enums) in parallel; T006 waits on
  all three; T007 waits on T002; T008 waits on T005-T007.
- Within US1: T009 parallel with nothing yet pending T004/T006; T012-T020
  (tests + all four frontend pages + both sign-in link edits) all
  parallel once T010/T011 land, since each touches a distinct file.
- US2's T023 and US3's T026/T027 are each parallel with the other
  story's tasks, since they touch disjoint files.
- T030 (depends only on T008) and T031 (depends on T008 plus every
  story's wiring -- T010/T011, T021/T022, T024/T025 -- since it exercises
  all three trigger points) run in parallel with each other once their
  own dependencies are met.

---

## Parallel Example: User Story 1

```bash
# After T010/T011 (endpoints) land, launch together:
Task: "Unit tests for reset_tokens.py in backend/tests/unit/test_reset_tokens.py"
Task: "Integration tests for guardian password-reset flow in backend/tests/integration/test_auth_guardian_password_reset.py"
Task: "Integration tests for instructor password-reset flow in backend/tests/integration/test_auth_instructor_password_reset.py"
Task: "Create guardian forgot-password page in frontend/src/app/(auth)/guardian/forgot-password/page.tsx"
Task: "Create guardian reset-password page in frontend/src/app/(auth)/guardian/reset-password/page.tsx"
Task: "Create instructor forgot-password page in frontend/src/app/(auth)/instructor/forgot-password/page.tsx"
Task: "Create instructor reset-password page in frontend/src/app/(auth)/instructor/reset-password/page.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) -> Phase 2 (Foundational) -> Phase 3 (US1).
2. **STOP and VALIDATE**: quickstart.md Scenarios 1-2 pass.
3. This alone closes the spec's stated motivating gap (no recovery path
   for a locked-out account) -- US2/US3 are lower-priority add-ons per
   spec.md's own priority rationale.

### Incremental Delivery

1. Setup + Foundational -> infrastructure ready.
2. Add US1 -> validate -> this is the MVP.
3. Add US2 -> validate -> registration confirmations now sent.
4. Add US3 -> validate -> deletion-request confirmations now sent,
   including the inactivity-sweep path.

### Suggested Task Count Summary

- Setup: 2 tasks
- Foundational: 6 tasks
- US1: 12 tasks (MVP)
- US2: 3 tasks
- US3: 4 tasks
- Polish: 4 tasks
- **Total: 31 tasks**
