# API Contract: Real-Account Deletion Pathway

**Feature**: `020-deletion-pathway` | **Date**: 2026-09-21

Extends `specs/010-instructor-classroom/`'s FastAPI backend and reuses
its session-cookie auth (`src/services/auth/dependencies.py`) unchanged.
Three new endpoints, plus one additive extension to the existing
`GET /api/auth/whoami` (FR-011, research.md R9) -- no existing field on
any endpoint is removed or changes meaning.

## `POST /api/deletion-requests` (NEW)

Auth: `current_session_claims` (either a guardian or an instructor
session; the authorization rule below depends on which). Rejects a
demo-account target (FR-007) and an unauthorized target (below) with
the same `403` shape, so a caller can't distinguish "not allowed" from
"doesn't exist" for someone else's account.

**Authorization** (who may request deletion of what):

| Requester | May target |
|---|---|
| Guardian | Themself (`target_type: "guardian"`, `target_id` = their own `guardian_id`), or any learner linked to them (`target_type: "learner"`, `learner.guardian_id == requester.guardian_id`) |
| Instructor | Themself (`target_type: "instructor"`), or any learner enrolled in one of their own rosters (`target_type: "learner"`) |

**Request** (learner or guardian target):
```json
{ "target_type": "learner", "target_id": "5b1e...e9f2" }
```

**Request** (instructor target, with optional successor):
```json
{
  "target_type": "instructor",
  "target_id": "9c22...af10",
  "transfer_rosters_to": "0a41...bb02"
}
```
`transfer_rosters_to` is only read when `target_type == "instructor"`;
omit it to have the async cascade delete the instructor's rosters
instead of transferring them (research.md R5). Ignored (not an error)
if present for a `learner`/`guardian` target.

**Response** `201`:
```json
{
  "deletion_request_id": "d1c4...2a90",
  "target_type": "learner",
  "target_id": "5b1e...e9f2",
  "status": "pending",
  "requested_at": "2026-09-21T14:03:00Z"
}
```

**Response** `403` -- requester is not authorized for this target, or
the target is a demo account. Generic `ForbiddenError("not_authorized")`
(`{"detail": "not_authorized"}`, codebase's existing convention) for
both, per the no-enumeration rule above -- no dedicated error class
needed since no extra field accompanies it.

**Response** `404` -- `target_id` does not resolve to an existing
account of the given `target_type`. Generic
`NotFoundError("target_not_found")` (`{"detail": "target_not_found"}`).

**Response** `409` -- a pending `DeletionRequest` already exists for
this exact `(target_type, target_id)` -- avoids creating duplicate
cascade work for the same target. Dedicated `DeletionAlreadyPendingError`
(the one new error class this feature adds, since it carries an extra
field): `{"error": "deletion_already_pending", "deletion_request_id": "..."}`.

## `GET /api/deletion-requests/{deletion_request_id}` (NEW)

Auth: `current_session_claims`. Authorized only if the caller's
account id matches the request's own `requested_by` (FR-009) -- returns
`403` (`ForbiddenError`) otherwise, never leaking whether the id exists
at all to anyone else.

**Response** `200` (pending):
```json
{
  "deletion_request_id": "d1c4...2a90",
  "target_type": "learner",
  "status": "pending",
  "requested_at": "2026-09-21T14:03:00Z",
  "completed_at": null
}
```

**Response** `200` (completed):
```json
{
  "deletion_request_id": "d1c4...2a90",
  "target_type": "learner",
  "status": "completed",
  "requested_at": "2026-09-21T14:03:00Z",
  "completed_at": "2026-09-22T06:00:00Z"
}
```

No field on this response ever includes any of the target's own data
(display name, email, mastery state, etc.) -- by design, per FR-009,
and trivially true once `status == "completed"` since that data no
longer exists.

**Response** `403` -- `{"detail": "not_authorized"}`, whether the id
doesn't exist or belongs to a different requester (same
no-enumeration reasoning as the submission endpoint).

## `GET /api/cron/execute-deletions` (NEW)

Auth: `Authorization: Bearer $CRON_SECRET`, identical pattern to the
existing `/api/cron/reset-demo-data` and `/api/cron/classify-
misconceptions` routes (`src/api/routes/cron.py`) -- `503` if
`CRON_SECRET` isn't configured, `401` if the provided secret doesn't
match.

Scheduled daily in `vercel.json`'s `crons` array (research.md R1/R8).
Runs two phases per invocation:

1. **Inactivity sweep** (FR-005): for every `RetentionRecord` with
   `enrollment_status = "inactive"` and `became_inactive_at` more than
   one year ago that has no existing pending `DeletionRequest` for its
   `(account_type, account_id)`, creates one (`requested_by =
   "system:inactivity-sweep"`). Before that check, also reconciles
   `inactivity_warning_sent_at` on every `RetentionRecord` (FR-011,
   research.md R10) via two mutually exclusive, ordered checks: first,
   if `enrollment_status = "active"`, clear a set value back to `NULL`
   regardless of `became_inactive_at`; otherwise, if
   `enrollment_status = "inactive"` and the record crosses
   `became_inactive_at + (1 year - 7 days)` while still `NULL`, set it
   to `now()` (always at least 7 days before that same record becomes
   eligible for the deletion-request creation later in this same
   phase). The `enrollment_status = "inactive"` guard on the set branch
   prevents a stale, pre-reactivation `became_inactive_at` from
   re-triggering a warning on an active account.
2. **Execution**: processes up to `MAX_DELETIONS_PER_RUN` pending
   `DeletionRequest` rows, oldest `requested_at` first, running the
   matching cascade from `data-model.md` for each inside its own
   transaction, setting `completed_at` only once that transaction
   commits. A request whose target no longer exists (already deleted by
   an earlier, concurrent path) is marked completed immediately without
   error (spec.md's Edge Cases).

**Response** `200`:
```json
{
  "status": "ok",
  "swept_count": 2,
  "processed_count": 5,
  "remaining_pending_count": 1
}
```

`remaining_pending_count` mirrors the Misconception Classifier's
watermark-deferral pattern (`tech-stack.md`) -- a nonzero value here is
expected and fine as long as it clears within the 30-day SLA (SC-001),
not evidence of a bug on its own.

## `GET /api/auth/whoami` (EXTENDED)

Unchanged for an unauthenticated caller and for every existing field.
Adds one new optional field, populated only for a guardian or
instructor session (FR-011, research.md R9):

```json
{
  "account_type": "guardian",
  "identifier": "parent@example.com",
  "pending_deletion_warnings": [
    {
      "target_type": "learner",
      "target_id": "5b1e...e9f2",
      "warned_at": "2026-09-14T06:00:00Z",
      "scheduled_deletion_date": "2026-09-21"
    }
  ]
}
```

`pending_deletion_warnings` is an empty list (never omitted, never
`null`) when the caller has no linked account with
`inactivity_warning_sent_at` set -- the common case. `scheduled_deletion_date`
is computed as `became_inactive_at + 1 year`, not stored separately.
For a guardian, one entry per linked learner whose `RetentionRecord`
carries a warning; for an instructor, at most one entry, for their own
account. A demo session (`account_type: "demo_instructor"`) always gets
an empty list -- demo accounts are never inactivity-tracked (FR-007).
