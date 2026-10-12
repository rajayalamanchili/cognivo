# Quickstart: Account Email Notifications

**Feature**: `045-account-email-notifications` | **Date**: 2026-10-12

## Prerequisites

- Backend running locally (`backend/`'s existing `uv run uvicorn
  src.api.main:app --reload`, per the repo's own quickstart) against a
  migrated dev database (`alembic upgrade head` after this feature's
  migration lands).
- `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS`, `FRONTEND_BASE_URL` set in
  `backend/.env` (research.md §6). A real Resend API key is only
  required to see an actual email arrive -- every scenario below is
  independently verifiable via `notification_log_entries` even with a
  deliberately-wrong key (the send fails, the action still succeeds,
  FR-012).

## Scenario 1: Password reset end to end (US1)

1. Register a real guardian: `POST /api/auth/guardian/register`
   `{"email": "demo-reset@example.com", "password": "correcthorse1"}`.
2. Request a reset: `POST /api/auth/guardian/forgot-password`
   `{"email": "demo-reset@example.com"}` -> expect `204`.
3. Read the raw token out of the dev database (`SELECT token_hash FROM
   password_reset_tokens ...` won't give you the raw value -- for local
   testing, temporarily log the raw token in `forgot_password_guardian`
   before it's hashed, or read it from the actual email if a real
   `RESEND_API_KEY` is configured).
4. Complete the reset: `POST /api/auth/guardian/reset-password`
   `{"token": "<raw-token>", "new_password": "newpassword123"}` ->
   expect `200` with a fresh session cookie set.
5. Confirm old credentials fail: `POST /api/auth/guardian/login` with
   the original password -> expect `401`.
6. Confirm new credentials work: same endpoint with the new password ->
   expect `200`.
7. Re-use the same token: repeat step 4 -> expect `422
   reset_token_invalid`.

## Scenario 2: No-enumeration check (SC-003)

1. `POST /api/auth/guardian/forgot-password` with an email that has no
   matching account -> expect `204`, byte-identical to step 2 above.
2. Confirm no row was written to `password_reset_tokens` for this
   non-existent account (no token to find), but no error either.

## Scenario 3: Registration confirmation (US2)

1. `POST /api/auth/instructor/register` with a fresh email.
2. Query `notification_log_entries` for
   `notification_type = 'registration'` and that account's id -> expect
   one row, `status = 'sent'` (or `'failed'` with a real but invalid
   `RESEND_API_KEY`, which is also a valid pass -- the point is a row
   exists at all, FR-013).

## Scenario 4: Deletion-request confirmation, both paths (US3)

1. As a guardian, enroll a learner, then `POST /api/deletion-requests`
   `{"target_type": "learner", "target_id": "<learner_id>"}` -> expect
   `201`.
2. Query `notification_log_entries` for
   `notification_type = 'deletion_request_confirmation'` -> expect one
   row whose `account_id` is the *guardian's* id, not the learner's
   (US3 Acceptance Scenario 2).
3. Submit a duplicate request for the same target -> expect `409`, and
   confirm no second `notification_log_entries` row was added (FR-008's
   "a rejected... duplicate deletion request MUST NOT send one").

## Scenario 5: Demo-account exclusion (FR-011)

1. Using a seeded demo guardian/instructor account (or the demo
   learner), attempt any of the three trigger points above.
2. Confirm zero `notification_log_entries` rows are written for that
   account at all -- not even a `failed` one, since `notify_*`'s
   `is_demo` guard short-circuits before any send attempt or log write
   (research.md §5).
