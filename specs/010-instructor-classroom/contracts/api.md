# API Contract: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review

**Feature**: `010-instructor-classroom` | **Date**: 2026-08-23

Extends `specs/001-domain-agnostic-core/contracts/api.md`'s FastAPI
backend with a new authenticated surface. Every route below except
`/api/auth/*` and the demo entry points requires a valid session cookie
(tech-stack.md's Authentication section) -- an instructor route rejects
a guardian's session and vice versa.

## Auth

### `POST /api/auth/guardian/register`

```json
{ "email": "parent@example.com", "password": "..." }
```
`201`, sets the session cookie:
```json
{ "guardian_id": "..." }
```
`409 email_taken` if already registered as a guardian (independently of
whether that email exists as an instructor, research.md §2).

### `POST /api/auth/instructor/register`

Same shape as above, scoped to `RealInstructorAccount`.

### `POST /api/auth/guardian/login` / `POST /api/auth/instructor/login`

```json
{ "email": "parent@example.com", "password": "..." }
```
`200`, sets the session cookie, same response shape as register.
`401 invalid_credentials` on mismatch -- deliberately identical whether
the email doesn't exist or the password is wrong (no account
enumeration).

### `POST /api/auth/logout`

No body. `204`. Clears the session cookie.

### `POST /api/learners` (guardian-authenticated)

```json
{ "display_name": "Jamie" }
```
`201`:
```json
{ "learner_id": "...", "guardian_id": "..." }
```
Creates a `LearnerProfile` row with `is_demo: false`, this guardian's
`guardian_id`, and a `RetentionRecord` in the same transaction
(spec 009 SC-004).

## Rosters

### `POST /api/rosters` (instructor-authenticated)

```json
{ "subject_id": "biology", "enrollment_mode": "open" }
```
`201`:
```json
{ "roster_id": "...", "subject_id": "biology", "enrollment_mode": "open", "join_code": "BIO-7F2K" }
```
`join_code` is `null` in the response when `enrollment_mode: "closed"`.

### `PATCH /api/rosters/{roster_id}` (instructor-authenticated, owner only)

```json
{ "enrollment_mode": "closed" }
```
`200`, same shape as create. `403` if the requesting instructor doesn't
own this roster (FR-010).

### `GET /api/rosters` (instructor-authenticated)

`200`:
```json
{ "rosters": [{ "roster_id": "...", "subject_id": "biology", "enrollment_mode": "open" }] }
```
Only the requesting instructor's own rosters -- never another
instructor's (FR-010, SC-002).

### `POST /api/rosters/join` (guardian-authenticated)

```json
{ "learner_id": "...", "join_code": "BIO-7F2K" }
```
For an `open` roster: `201`, enrollment completes immediately:
```json
{ "status": "enrolled", "enrollment_id": "..." }
```
For a `closed` roster's code: `202`, a pending request is created:
```json
{ "status": "pending", "enrollment_request_id": "..." }
```
A second attempt for the same (`learner_id`, roster) pair while a
request is already pending returns the existing pending request's
`202` rather than creating a duplicate (Edge Cases).
`404 invalid_join_code` for an unknown code.

### `GET /api/rosters/{roster_id}/requests` (instructor-authenticated, owner only)

`200`:
```json
{ "requests": [{ "enrollment_request_id": "...", "learner_id": "...", "requested_at": "..." }] }
```
Only pending (`decision: null`) requests.

### `POST /api/rosters/{roster_id}/requests/{enrollment_request_id}/approve` (instructor-authenticated, owner only)

No body. `200`:
```json
{ "status": "approved", "enrollment_id": "..." }
```
Creates the `Enrollment` row, recording this instructor as
`authorized_by` (spec 009 FR-011).

### `POST /api/rosters/{roster_id}/requests/{enrollment_request_id}/decline` (instructor-authenticated, owner only)

No body. `200`:
```json
{ "status": "declined" }
```

### `GET /api/rosters/{roster_id}/enrollments` (instructor-authenticated, owner only)

Added during Phase 4 implementation (`/speckit-clarify` with the
user) -- the roster-management page's "view enrolled learners with an
unenroll action" (tasks.md T035) has no other source for who's
currently enrolled: `GET /api/rosters/{roster_id}/dashboard` below
also carries this, but bundled with a full weak-area report this
endpoint deliberately never computes.

`200`:
```json
{ "enrollments": [{ "learner_id": "...", "display_name": "Jamie" }] }
```

### `DELETE /api/rosters/{roster_id}/enrollments/{learner_id}` (instructor-authenticated, owner only, OR the enrolled learner's own guardian)

`204`. Removes the `Enrollment` row (FR-007a) -- never a
`DeletionRequest`, never touches the learner's account/data.

## Dashboard

### `GET /api/rosters/{roster_id}/dashboard` (instructor-authenticated, owner only)

`200`:
```json
{
  "roster_id": "...",
  "subject_id": "biology",
  "learners": [
    {
      "learner_id": "...",
      "display_name": "Jamie",
      "recommendations": { "...": "byte-for-byte GET /api/learners/{id}/recommendations response (SC-001)" }
    }
  ]
}
```
Each `recommendations` object is exactly what
`GET /api/learners/{learner_id}/recommendations?subject_id={roster.subject_id}`
already returns for that learner directly -- this endpoint fans out to
that same function once per enrolled learner (FR-008, research.md §4),
never a separate computation.

## Content review

### `GET /api/content-review/flagged` (instructor-authenticated)

`200`:
```json
{
  "flagged": [
    {
      "question_id": "...",
      "learner_id": "...",
      "roster_id": "...",
      "stem": "...",
      "flagged_reason": "...",
      "flagged_at": "..."
    }
  ]
}
```
Scoped server-side to flagged questions belonging to a learner enrolled
in one of the requesting instructor's own rosters (FR-011, joined
through `Enrollment` at query time -- research.md §5). Empty array, not
an error, when there's nothing to review.

### `POST /api/content-review/{question_id}/resolve` (instructor-authenticated)

```json
{ "action": "reactivate" }
```
or
```json
{ "action": "reject" }
```
`200`:
```json
{ "question_id": "...", "validation_status": "valid" }
```
(`"flagged"` unchanged if `action: "reject"`.) Records a new audited
event (FR-013) capturing the resolving instructor, the action, and a
timestamp. `403` if the question doesn't belong to a learner on this
instructor's roster(s) (FR-011).

## Demo entry points

### `GET /api/demo-instructor` (extends Milestone 1's existing `GET /api/demo-learner`)

`200`:
```json
{ "instructor_id": "...", "display_name": "Demo Instructor" }
```
No authentication required to *call* -- same public, no-session pattern
as the existing demo-learner endpoint. Resolves to the seeded
`DemoInstructorProfile`.

Unlike `GET /api/demo-learner`, this response also sets the session
cookie (`/speckit-clarify` with the user, Phase 7 implementation):
the demo instructor's rosters/dashboard/content-review are all real,
session-gated routes (Milestone 1's learner routes predate auth
entirely, so the demo-learner endpoint never needed to issue one) --
without a cookie here, the demo instructor would be name-only and
`current_instructor` would 401 on every other instructor route. The
session claim's account type is the distinct `demo_instructor` (not
`instructor`), so `current_instructor` resolves it against
`DemoInstructorProfile` rather than `RealInstructorAccount`.
`ClassroomRoster.instructor_id` is consequently not a FK to either
table alone (migration `7e686faa5e6d`) -- same "could point at more
than one table" shape as `RetentionRecord.account_id`/
`DeletionRequest.target_id`, enforced at the application layer instead.
