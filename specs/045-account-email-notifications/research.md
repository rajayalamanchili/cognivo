# Research: Account Email Notifications

**Feature**: `045-account-email-notifications` | **Date**: 2026-10-12

## §1. Outbound email provider

**Decision**: Resend (`https://api.resend.com/emails`), called directly
via a plain `httpx.post(...)` REST call -- no `resend` SDK dependency
added. `httpx` is promoted from this project's `dev` dependency group
to its main `dependencies` (it is already resolved/installed as
FastAPI's test-client dependency; this only changes which group
declares it, not what gets installed).

**Rationale**: No outbound email provider is locked anywhere in
`tech-stack.md` today -- this is the first feature that needs one.
Resend's REST API is a single `POST` with a JSON body and a bearer
token, needing nothing beyond a fetch-capable HTTP client this project
already has resolved. SendGrid and Postmark's APIs are comparably
simple but have no existing foothold here either, so they don't win on
"already in this codebase." AWS SES was rejected the same way this
project already rejected Supabase's bundled services (tech-stack.md's
Data layer section) -- it would be the first AWS account/IAM surface
in a project that otherwise has none, for a need a two-line REST call
already covers. Not adding the `resend` PyPI package itself keeps this
feature's one true new dependency to zero: `httpx` was already going to
be in `uv.lock` either way.

**Alternatives considered**: `resend` Python SDK (rejected -- it's a
thin wrapper over the same REST call `httpx` already makes, so it would
be a second way to do one HTTP POST); SendGrid (rejected -- heavier,
more verbose API for the same transactional-email need, no existing
foothold); AWS SES (rejected -- new cloud-provider account/IAM surface
for a single-purpose need, see above); SMTP directly via stdlib
`smtplib` (rejected -- would need a mail-sending domain/relay
configured independently of any provider's deliverability/reputation
tooling, which a transactional-email provider bundles for free).

## §2. Password reset token storage and shape

**Decision**: A new `password_reset_tokens` table. The link emailed to
the user carries a high-entropy random value (`secrets.token_urlsafe(32)`,
~256 bits), generated once and never stored directly -- only its SHA-256
hex digest is persisted (`token_hash`), the same "never store the
verifier" principle as a password hash, but using a fast hash rather
than Argon2: unlike a user-chosen password, this token already has
enough entropy that a slow, memory-hard hash buys nothing against
brute-force guessing, and a reset-link verification happening on every
page load of the reset-password screen (not just once at submit) is a
better fit for a cheap comparison.

`account_type` reuses the existing `AuthorizedByType` enum
(`GUARDIAN`/`INSTRUCTOR` -- `src/models/enums.py`) rather than adding a
new one; its two members are exactly what this table needs.
`account_id` is deliberately not a foreign key, mirroring
`DeletionRequest.target_id`/`RetentionRecord.account_id`'s existing
precedent for a column that must point at one of two different tables
depending on a sibling enum column.

**At most one valid (unused) token per account** (FR-004) is enforced
two ways, mirroring `DeletionRequest`'s existing pending-uniqueness
pattern:
1. Application logic: issuing a new token first `UPDATE`s any existing
   `used_at IS NULL` row for that `(account_type, account_id)` to
   `used_at = now()` (reusing `used_at` as the one "no longer valid"
   marker -- no separate "invalidated" state needed, since the spec
   never distinguishes "someone used this link" from "a newer link
   superseded it").
2. A partial unique index, `uq_password_reset_tokens_pending_account`
   on `(account_type, account_id)` `WHERE used_at IS NULL`, as the
   actual race-proof arbiter for two concurrent reset requests (same
   reasoning as `deletion_requests`' own partial unique index, PR #79's
   review comment on that table). On the rare `IntegrityError` this
   produces, the route retries the invalidate-then-insert once (a
   self-request racing itself across two tabs, not adversarial input,
   so a single retry is the right lazy fix rather than a longer
   back-off loop).

**Expiry**: `expires_at` set to `created_at + timedelta(hours=1)` at
issuance (FR-003's "on the order of an hour"), checked at verification
time rather than swept/deleted -- an expired row stays in the table as
part of `NotificationLogEntry`-adjacent audit history rather than being
cleaned up, since nothing in this spec requires reclaiming that storage
and a cron-based sweep would be new scope not asked for.

## §3. Reset-request rate limiting without an enumeration leak

**Decision**: No new counter column. Before issuing a token, the
forgot-password route checks whether an existing token (used or not)
for that account was `created_at` within the last 60 seconds
(`RESET_REQUEST_MIN_INTERVAL`); if so, it silently skips issuing a new
token and sending an email, and still returns the exact same success
response as every other case.

**Rationale**: SC-003 requires the forgot-password response to be
identical whether or not the email matches a real account -- a `429`
(this codebase's existing `RateLimitedError`, used by login lockout)
would itself leak "this account exists and was just reset-requested."
A silent no-op preserves FR-002's identical-response guarantee while
still bounding how many emails one requester can trigger per account
per minute. Unlike `login_guardian`'s lockout check, this path has no
expensive operation (no Argon2 verify) whose *timing* would otherwise
leak account existence, so no `_DUMMY_PASSWORD_HASH`-style constant-cost
work is needed here to match `auth.py`'s existing precedent -- that
precedent exists specifically to equalize two paths with different
real costs, which doesn't apply to a token `INSERT`.

## §4. Notification audit log

**Decision**: A new `notification_log_entries` table (the spec's
"Notification Log Entry" key entity), not a reuse of
`AssessmentEventType`/`AssessmentEvent`. That table's own docstring
scopes it to pedagogical audit trail (FR-010/SC-006 of spec 001) tied
to a `learner_id` and a `(subject_id, topic_id)` FK pair -- neither
concept applies to a guardian/instructor-level email attempt, and
overloading it would mean a nullable `learner_id` on a table whose
existing index/FK shape assumes one always exists.

Two new enums in `src/models/enums.py`:
```python
class NotificationType(enum.StrEnum):
    REGISTRATION = "registration"
    PASSWORD_RESET = "password_reset"
    DELETION_REQUEST_CONFIRMATION = "deletion_request_confirmation"

class NotificationStatus(enum.StrEnum):
    SENT = "sent"
    FAILED = "failed"
```
`account_type` reuses `AuthorizedByType` again (same reasoning as §2).
`account_id` is not a FK (same reasoning as §2 and `DeletionRequest`) --
a deletion-request-confirmation log row for a just-deleted account must
be able to outlive that account's row, which a FK would forbid without
`ON DELETE SET NULL` semantics this feature doesn't need.

## §5. Where email-sending/logging lives, and the demo-account guard

**Decision**: `backend/src/services/notifications/mailer.py` (the raw
Resend `httpx` call, returns `bool`, never raises -- any exception or
non-2xx response is caught and treated as a failure) and
`backend/src/services/notifications/notify.py` (three functions,
`notify_registration`, `notify_password_reset`, `notify_deletion_request`,
one per `NotificationType` member) are the only two new modules. Each
`notify_*` function:
1. Takes `is_demo: bool` as a required keyword argument and returns
   immediately -- no send attempt, no log row -- if `True`. This is
   enforced *inside* the shared function precisely because Constitution
   Principle VIII's demo-account exclusion (FR-011) is a hard
   requirement, not a per-caller judgment call: a required parameter
   that every call site must supply is harder to silently forget than a
   convention of "check `is_demo` before calling," which is how every
   other demo-account guard in this codebase (`deletion.py`'s
   `target.is_demo` checks) is currently written at the call site
   instead.
2. Calls `mailer.send_email(...)`, then writes exactly one
   `NotificationLogEntry` row (`status=SENT` or `FAILED`) and commits it
   on the same `db` session the caller passed in -- a logging failure
   here is already just a second Postgres write on an open session, not
   a new failure mode needing its own isolation.
3. Never raises (FR-012) -- a failed send is logged, not propagated.

**Call sites** (all three, after their existing triggering action's own
commit has already succeeded):
- `register_guardian`/`register_instructor` (`auth.py`) --
  `notify_registration`. `is_demo=False` always (these two endpoints
  never create a demo account, `AuthCredentialsIn` row-ignoring note
  already in `auth.py`'s own docstring).
- `submit_deletion_request` (`deletion.py`) -- `notify_deletion_request`,
  recipient resolution: `target_type == LEARNER` looks up the managing
  guardian via `LearnerProfile.guardian_id` (US3 Acceptance Scenario 2:
  the learner has no email of their own); `GUARDIAN`/`INSTRUCTOR` notify
  the target account itself. The existing `target.is_demo` check earlier
  in that same function already rejects a demo target before this point,
  so the `is_demo` passed through here is always the *recipient's* own
  flag (a demo guardian cannot itself legally own a non-demo learner, so
  this reduces to "the one already-checked flag" in every case the
  current data model allows).
- `sweep_inactive_accounts` (`inactivity.py`, FR-009) -- same
  `notify_deletion_request` call, immediately after each individual
  `DeletionRequest`'s own `db.commit()` (restructured from one batched
  commit at the end of the loop to a per-record commit, so a
  notification is only ever sent for a request that's actually
  persisted, and one record's failure can't roll back a sibling's
  already-sent notification). `RetentionAccountType` has no `GUARDIAN`
  member today (only `LEARNER`/`INSTRUCTOR` -- guardians aren't
  inactivity-swept, confirmed by reading `enums.py` and every
  `RetentionRecord(...)` construction site), so this path's recipient
  resolution is the same two cases as above minus the
  guardian-target-itself case.

## §6. Reset-link frontend route and new env vars

**Decision**: Three new env vars in `backend/.env.example`:
`RESEND_API_KEY`, `EMAIL_FROM_ADDRESS` (e.g.
`Cognivo <noreply@cognivo.app>`), and `FRONTEND_BASE_URL` (e.g.
`https://cognivo.vercel.app` or `http://localhost:3000` locally) --
the backend needs the last one to build an absolute reset link inside
the email body, since it has no other way to know the frontend's own
deployed origin (no existing env var covers this; `GRADING_AGENT_URL`/
`TUTOR_AGENT_URL` are the opposite direction, frontend-adjacent
services the backend calls out to, not an inbound-facing base URL).

Reset links point at `{FRONTEND_BASE_URL}/guardian/reset-password?token=...`
or `{FRONTEND_BASE_URL}/instructor/reset-password?token=...` depending
on which role's forgot-password form was submitted (spec's own
Assumptions: the role is already known from which sign-in page the
request came from). Four new Next.js pages under the existing
`(auth)/guardian/` and `(auth)/instructor/` route groups
(`forgot-password/page.tsx`, `reset-password/page.tsx` each), plus a
one-line "Forgot password?" link added to the two existing
`sign-in/page.tsx` files. No new design-system work -- these reuse the
form components spec 041/043's redesigns already locked for this
project's sign-in/register pages.

## §7. Vercel execution-time fit

**Decision**: `httpx.post(...)` to Resend is given an explicit 10-second
timeout. Per tech-stack.md's Deployment-target section (Milestone 6's
lesson: an unbounded third-party call inside a request handler risks
the function's `maxDuration`), 10s leaves ample headroom under the
backend's existing `maxDuration: 30` even stacked behind this request's
own DB work, with no change to `vercel.json` needed -- registration,
reset-request, and deletion-request submission were already
comfortably sub-second requests before this feature, and the new email
step runs after each one's own commit, not blocking it structurally
the way Milestone 6's synchronous Grading Agent call did.

## §8. Scope confirmation: FR-010 and completion emails

**Decision**: Confirmed by inspection, not revisited -- `execute.py`'s
deletion cascade genuinely hard-deletes the target row (spec 009), so
no email address survives to notify at completion time without a new
"snapshot the address before deleting" mechanism. Per spec.md FR-010,
this is deliberately out of scope; no data-model change is needed to
support it.
