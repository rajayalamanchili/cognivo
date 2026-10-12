# API Contract: Account Email Notifications

**Feature**: `045-account-email-notifications` | **Date**: 2026-10-12

Extends `src/api/routes/auth.py` (four new endpoints) and
`src/api/routes/deletion.py` (no new endpoint, additive side effect
only -- see research.md §5). No existing endpoint's request/response
shape changes.

## `POST /api/auth/guardian/forgot-password` (NEW)

Auth: none (mirrors `register_guardian`/`login_guardian` -- unauthenticated
by definition, since the caller is locked out).

**Request**:
```json
{ "email": "guardian@example.com" }
```

**Response** `204` -- always, regardless of whether `email` matches a
real, non-demo `RealGuardianAccount` (FR-002/SC-003: no
account-enumeration signal). Internally: looks up the account; if found,
not demo, and no token was issued for it in the last 60 seconds
(research.md §3), invalidates any still-valid prior token, issues a new
one, and sends the reset email. Every other case (no match, demo match,
rate-limited) does nothing further but returns the identical `204`.

## `POST /api/auth/guardian/reset-password` (NEW)

Auth: none (the token itself is the credential).

**Request**:
```json
{ "token": "<raw-token-from-the-emailed-link>", "new_password": "..." }
```
`new_password` carries the same `min_length=8` constraint as
`ChangePasswordIn.new_password`.

**Response** `200` (mirrors `GuardianAuthOut`, sets the session cookie
exactly like `login_guardian`):
```json
{ "guardian_id": "..." }
```

**Response** `422` -- `{"detail": "reset_token_invalid"}` (no matching
`token_hash`, or the matching row's `used_at` is already set) or
`{"detail": "reset_token_expired"}` (`expires_at` has passed).
`UnprocessableError`, this codebase's existing generic 422 shape -- no
new error class, same precedent as `GuardianMeIn`'s per-field
`f"{field}_required"` strings sharing one class.

**Side effects on success** (FR-005/FR-006, mirrors
`change_guardian_password` exactly): sets a new `password_hash`, sets
`password_changed_at = now()` (invalidates every other existing
session token on its next use), marks the token's `used_at = now()`,
and issues a fresh session cookie for the caller's own browser.

## `POST /api/auth/instructor/forgot-password` (NEW)

Identical contract to the guardian endpoint above, targeting
`RealInstructorAccount` instead. `204` always.

## `POST /api/auth/instructor/reset-password` (NEW)

Identical contract to the guardian endpoint above, targeting
`RealInstructorAccount` instead, response mirrors `InstructorAuthOut`
(`{"instructor_id": "..."}`), same `422 reset_token_invalid` /
`reset_token_expired` shape.

## No new endpoint: deletion-request confirmation and registration confirmation

FR-007/FR-008/FR-009 are side effects of three existing endpoints
(`register_guardian`, `register_instructor`,
`POST /api/deletion-requests`) and one existing cron job
(`GET /api/cron/execute-deletions`'s `sweep_inactive_accounts` step) --
none of their request/response contracts change. A failed email send
never changes any of their existing response codes (FR-012) -- the
contract is "this response is identical whether or not the email
succeeded," which is a property of the *implementation*, not a new wire
shape to document here.
