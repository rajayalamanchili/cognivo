# API Contract Changes: Instructor-Facing UI Redesign and Default-Instructor Self-Service

Conventions follow this project's existing contract docs (e.g. spec
041's `contracts/api-changes.md`): only deltas from the current, live
API are documented here; endpoints not mentioned are unchanged.

## 1. `POST /api/auth/instructor/change-password` (NEW)

Mirrors `POST /api/auth/guardian/change-password` exactly.

**Request** (instructor session cookie required):
```json
{ "current_password": "string", "new_password": "string (min 8 chars)" }
```

**Response**: `204 No Content`. A fresh session cookie is set on
success (same as the guardian endpoint).

**Errors**:
- `403 demo_account` -- session resolves to a `DemoInstructorProfile`
  (no password to change).
- `401 invalid_credentials` -- `current_password` doesn't match.
- `429` -- account is lockout-throttled (same mechanism as login).

## 2. `PATCH /api/auth/instructor/me` (EXTENDED)

Existing endpoint (spec 041 FR-017) gains six new optional fields,
`exclude_unset` semantics identical to `GuardianMeIn` -- omitting a
field never resets it.

**Request** (all fields optional; existing `display_name` unchanged):
```json
{
  "display_name": "string (min 1 char)",
  "theme": "system | light | dark",
  "larger_text": true,
  "reduce_motion": false,
  "notifications_enabled": true,
  "default_enrollment_mode": "open | closed",
  "default_due_date_offset_days": 7
}
```
`default_due_date_offset_days` may be sent as `null` explicitly to mean
"no due date by default"; a positive integer otherwise.

**Response**:
```json
{
  "display_name": "string",
  "theme": "system | light | dark",
  "larger_text": true,
  "reduce_motion": false,
  "notifications_enabled": true,
  "default_enrollment_mode": "open | closed",
  "default_due_date_offset_days": 7
}
```

**Errors**:
- `403 demo_account` -- any of the five new fields (not
  `display_name`) is present in the request body and the session
  resolves to a `DemoInstructorProfile`.
- `422 default_due_date_offset_days_invalid` -- a non-null value `<= 0`.

## 3. `GET /api/auth/whoami` (EXTENDED)

`WhoAmIOut` gains the same five preference fields (not
`notifications_enabled`'s backend-send behavior, just its stored
value) as optional, `None` for every non-instructor session -- mirrors
the existing `_GUARDIAN_ONLY_FIELDS` pattern with a new
`_INSTRUCTOR_ONLY_FIELDS` list:

```json
{
  "account_type": "instructor",
  "theme": "system | light | dark",
  "larger_text": false,
  "reduce_motion": false,
  "notifications_enabled": true,
  "default_enrollment_mode": "open | closed",
  "default_due_date_offset_days": null
}
```

## 4. `POST /api/deletion-requests` (UNCHANGED -- reused)

Settings' two new Privacy actions (request a learner's data deletion;
request own-account deletion) call this existing endpoint exactly as
it exists today, with `target_type: "learner" | "instructor"`. No
request/response shape change. See `backend/src/api/routes/
deletion.py` and spec 020's own contract for the full shape.

## 5. `GET /api/learners/{learner_id}/enrollments` (EXTENDED)

One new field per entry, additive only:

```json
{
  "enrollments": [
    {
      "roster_id": "uuid",
      "subject_id": "string",
      "is_default_instructor_roster": true
    }
  ]
}
```

## 6. `POST /api/learners/{learner_id}/rosters/{roster_id}/assignments` (NEW)

Guardian-authenticated. Lets a guardian assign a quiz to their own
learner, but only on a roster owned by the default instructor.

**Request**:
```json
{
  "topic_ids": ["string"],
  "question_count": 5,
  "due_at": "2026-10-20T00:00:00Z"
}
```
`due_at` is optional (`null`/omitted = no due date), same semantics as
the instructor-side endpoint's field of the same name. No
`learner_ids` field -- the path's `learner_id` is the sole target.

**Response** (`201`):
```json
{
  "assignment_id": "uuid",
  "roster_id": "uuid",
  "subject_id": "string",
  "topic_ids": ["string"],
  "question_count": 5,
  "due_at": "2026-10-20T00:00:00Z",
  "target_learner_ids": ["uuid"]
}
```
Same `CreateAssignmentOut` shape the instructor-side endpoint already
returns -- this endpoint is a thin, authorization-narrowed wrapper
around the same `create_assignment()` service call.

**Errors**:
- `404 unknown_roster_id` -- `roster_id` doesn't exist at all, same
  convention as the instructor-side endpoint's `_get_owned_roster`.
- `403 not_your_learner` -- `learner_id` doesn't belong to the calling
  guardian.
- `403 not_enrolled` -- the learner isn't enrolled in `roster_id`.
- `403 not_default_instructor_roster` -- `roster_id` isn't owned by
  the default instructor.
- `404 unknown_topic_id` / `422 empty_target` -- same as the
  instructor-side endpoint (delegated to the same `create_assignment()`
  validation).
