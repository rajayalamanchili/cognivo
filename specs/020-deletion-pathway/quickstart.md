# Quickstart: Real-Account Deletion Pathway

**Feature**: `020-deletion-pathway` | **Date**: 2026-09-21

Validates all three user stories end to end against a real dev
database. Prerequisites: Milestone 7 (real guardian/instructor/learner
accounts) already runnable locally, `DATABASE_URL` reachable, and
`CRON_SECRET` set for the cron-executor scenarios.

## Setup

```bash
cd backend
alembic upgrade head   # no new migration expected -- confirms this feature added none
python scripts/seed_synthetic_family.py   # seed script: one guardian, two learners with mastery
                                           # state/assessment events/generated questions, one
                                           # instructor with a roster both learners are enrolled in
```

If no such seed script exists yet, seed equivalently via the existing
`/api/auth/guardian/register` + roster-join flow (spec 010's
quickstart) instead of writing a new one -- this feature doesn't need
its own fixture format beyond "a real account with real linked data."

## Scenario 1 -- User Story 1: guardian requests deletion of their learner (SC-001)

```bash
curl -s -X POST "$BACKEND_URL/api/deletion-requests" \
  -H "Content-Type: application/json" -b guardian-session-cookie.txt \
  -d '{"target_type": "learner", "target_id": "<learner-id>"}'
```

**Expected**: `201`, `status: "pending"`. Confirm nothing was deleted
yet -- mastery state, assessment events, and roster membership for this
learner all still exist.

```bash
curl -s -X GET "$BACKEND_URL/api/cron/execute-deletions" \
  -H "Authorization: Bearer $CRON_SECRET"
```

**Expected**: `200`, `processed_count: 1`. Then, for every table in
`data-model.md`'s learner cascade:

```bash
psql "$DATABASE_URL" -c "SELECT count(*) FROM mastery_states WHERE learner_id = '<learner-id>';"
psql "$DATABASE_URL" -c "SELECT count(*) FROM assessment_events WHERE learner_id = '<learner-id>';"
psql "$DATABASE_URL" -c "SELECT count(*) FROM generated_questions WHERE learner_id = '<learner-id>';"
psql "$DATABASE_URL" -c "SELECT count(*) FROM enrollments WHERE learner_id = '<learner-id>';"
psql "$DATABASE_URL" -c "SELECT count(*) FROM learner_profiles WHERE learner_id = '<learner-id>';"
```

**Expected**: every count is `0` (SC-001). The still-enrolled sibling
learner (same guardian) and the instructor's roster/dashboard both
still work normally -- confirm via `GET /api/rosters/{roster_id}` and
`GET /api/learners/{other_learner_id}/mastery` -- no dangling-reference
error, no cross-learner data loss.

## Scenario 2 -- User Story 2: automatic deletion after inactivity (SC-002)

```bash
psql "$DATABASE_URL" -c "
  UPDATE retention_records
  SET enrollment_status = 'inactive', became_inactive_at = now() - interval '400 days'
  WHERE account_id = '<other-learner-id>';
"
curl -s -X GET "$BACKEND_URL/api/cron/execute-deletions" \
  -H "Authorization: Bearer $CRON_SECRET"
```

**Expected**: `swept_count: 1` on this run (or the next, if already
past the sweep phase this run), followed by `processed_count`
incrementing on a subsequent run -- the account is deleted through the
identical cascade as Scenario 1, and a `DeletionRequest` row now exists
with `requested_by = "system:inactivity-sweep"`.

Re-run against a learner whose `became_inactive_at` is only 30 days
ago: **expected** no `DeletionRequest` is created (spec.md's Edge Cases,
"account regains active enrollment"/"less than a year" scenarios).

## Scenario 2b -- User Story 2: pre-deletion warning (FR-011, SC-006)

```bash
psql "$DATABASE_URL" -c "
  UPDATE retention_records
  SET enrollment_status = 'inactive', became_inactive_at = now() - interval '359 days'
  WHERE account_id = '<learner-id>';
"
curl -s -X GET "$BACKEND_URL/api/cron/execute-deletions" \
  -H "Authorization: Bearer $CRON_SECRET"
curl -s "$BACKEND_URL/api/auth/whoami" -b guardian-session-cookie.txt
```

**Expected**: `pending_deletion_warnings` contains one entry for
`<learner-id>` with a `scheduled_deletion_date` 6 days out, and
`retention_records.inactivity_warning_sent_at` is now set. Confirm no
`DeletionRequest` exists yet for this learner -- the warning fires
before the deletion trigger, never at the same moment. Then reactivate
the learner (`enrollment_status = 'active'`), re-run the cron, and
confirm `whoami`'s list no longer includes this learner and
`inactivity_warning_sent_at` is back to `NULL` (Acceptance Scenario 3).

## Scenario 3 -- User Story 3: requester checks completion status (SC-005)

```bash
curl -s "$BACKEND_URL/api/deletion-requests/<deletion_request_id>" -b guardian-session-cookie.txt
```

**Expected**: `status: "pending"` before the cron run, `status:
"completed"` with a `completed_at` timestamp after it -- and no field
in either response contains the target's own data (display name,
mastery state, etc.).

## Regression checks (SC-003, SC-004)

```bash
curl -s -X POST "$BACKEND_URL/api/deletion-requests" \
  -H "Content-Type: application/json" -b guardian-session-cookie.txt \
  -d '{"target_type": "learner", "target_id": "<already-deleted-learner-id>"}'
```
**Expected**: `404 target_not_found` (SC-003) -- not a duplicate or
partial deletion attempt.

```bash
curl -s -X POST "$BACKEND_URL/api/deletion-requests" \
  -H "Content-Type: application/json" -b instructor-session-cookie.txt \
  -d '{"target_type": "instructor", "target_id": "<own-instructor-id>", "transfer_rosters_to": "<successor-instructor-id>"}'
```
Run the cron executor, then confirm the roster's `instructor_id` now
equals the successor and every learner who was enrolled in it is still
present with intact mastery state (SC-004) -- the instructor's own
`real_instructor_accounts` row is gone, but no learner data moved or
disappeared.
