# Data Model: Account Email Notifications

**Feature**: `045-account-email-notifications` | **Date**: 2026-10-12

Two new tables. No existing table's schema changes.

## `PasswordResetToken` (new table: `password_reset_tokens`)

| Column | Type | Notes |
|---|---|---|
| `reset_token_id` | UUID, PK | `default=uuid.uuid4` |
| `account_type` | `AuthorizedByType` enum (`guardian`/`instructor`) | Reused enum, not a new one (research.md §2) |
| `account_id` | UUID, not null | Not a FK -- points at `real_guardian_accounts.guardian_id` or `real_instructor_accounts.instructor_id` depending on `account_type` (same non-FK pattern as `DeletionRequest.target_id`) |
| `token_hash` | String, not null, unique | SHA-256 hex digest of the raw token emailed to the user; the raw value itself is never persisted |
| `created_at` | timestamptz, not null | `server_default=func.now()` |
| `expires_at` | timestamptz, not null | `created_at + 1 hour` at issuance (FR-003) |
| `used_at` | timestamptz, nullable | Set on first successful use, or when a newer token for the same account supersedes this one (FR-004) -- `NULL` means "currently valid" |

**Indexes**:
- `uq_password_reset_tokens_pending_account`: unique partial index on
  `(account_type, account_id)` `WHERE used_at IS NULL` -- enforces
  "at most one valid token per account" (FR-004) at the DB level,
  mirroring `deletion_requests`' own pending-uniqueness index.

**Validity rule** (checked at verification time, not via a sweep):
a token is valid iff `used_at IS NULL AND expires_at > now()`.

## `NotificationLogEntry` (new table: `notification_log_entries`)

| Column | Type | Notes |
|---|---|---|
| `notification_log_id` | UUID, PK | `default=uuid.uuid4` |
| `notification_type` | `NotificationType` enum (new: `registration`/`password_reset`/`deletion_request_confirmation`) | One member per FR-007/FR-002/FR-008 |
| `account_type` | `AuthorizedByType` enum (`guardian`/`instructor`) | Reused enum (research.md §4) |
| `account_id` | UUID, not null | Not a FK -- must be able to outlive a deleted account (research.md §4) |
| `attempted_at` | timestamptz, not null | `server_default=func.now()` |
| `status` | `NotificationStatus` enum (new: `sent`/`failed`) | FR-012/FR-013 |
| `error_detail` | String, nullable | Populated only when `status = failed`; the caught exception's message or the provider's non-2xx response body, truncated |

**New enums** (`src/models/enums.py`):
```python
class NotificationType(enum.StrEnum):
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"
    DELETION_REQUEST_CONFIRMATION = "deletion_request_confirmation"


class NotificationStatus(enum.StrEnum):
    SENT = "sent"
    FAILED = "failed"
```

## Relationships to existing entities

- `PasswordResetToken.account_id` / `NotificationLogEntry.account_id`
  resolve against `RealGuardianAccount.guardian_id` or
  `RealInstructorAccount.instructor_id` depending on their sibling
  `account_type` column -- application-level resolution only, same as
  `DeletionRequest.target_id` and `RetentionRecord.account_id` already
  do.
- A deletion-request confirmation triggered by a `target_type ==
  LEARNER` submission resolves its `NotificationLogEntry.account_id` to
  the managing guardian's `guardian_id` (`LearnerProfile.guardian_id`),
  never the learner's own id -- `LearnerProfile` has no email/credential
  fields to notify (spec.md Assumptions).

## State transitions

`PasswordResetToken`: `valid` (`used_at IS NULL`, `expires_at` in the
future) -> `used` (first successful `reset-password` completion) or
`superseded` (a later token issued for the same account) -- both
transitions are the same `used_at = now()` write, since no requirement
distinguishes the two outcomes after the fact.

`NotificationLogEntry`: write-once, append-only -- no transitions.
