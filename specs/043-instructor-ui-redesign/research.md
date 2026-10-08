# Phase 0 Research: Instructor-Facing UI Redesign and Default-Instructor Self-Service

No `NEEDS CLARIFICATION` markers remain in `spec.md` -- every open
question was resolved directly with the user across four
`/speckit-clarify` passes (see `spec.md`'s Clarifications). This file
records the concrete implementation decisions those answers imply,
grounded in the actual existing code (checked directly, not assumed)
rather than re-opening anything already decided.

## 1. Instructor password change

**Decision**: Add `POST /api/auth/instructor/change-password`, a
line-for-line mirror of the existing `POST /api/auth/guardian/
change-password` (`backend/src/api/routes/auth.py`): same
`ChangePasswordIn` shape (`current_password`, `new_password`), same
lockout check (`is_locked_out`/`record_failed_attempt`/
`record_successful_attempt`), same re-issue-a-fresh-session-cookie
behavior after success, and (added during PR #111 review, after the
initial implementation shipped without it) the same
`password_changed_at`-based prior-session invalidation `RealGuardianAccount`
already has: a new, nullable `password_changed_at` column, set on every
successful change, checked by a new `instructor_session_revoked`
function mirroring `dependencies.py`'s existing `guardian_session_revoked`
and wired into `current_session_claims` the same way. Initially deferred
as an accepted gap under FR-013's then-eight-column bound; revisited
once review flagged that the default instructor is the one account in
this entire feature where a stolen, still-valid session actually
matters (it can reach every guardian-enrolled learner's roster data),
making the schema cost worth paying.

**Rationale**: The guardian endpoint already encodes every real
decision this needs (lockout-before-password-check ordering, session
re-issue so the caller's own tab doesn't get logged out) -- re-deriving
any of it would risk missing a fix already made there (e.g. the
fixed-cost dummy-hash login-enumeration guard, the PR #109 lockout
fix).

**Lockout**: `change_guardian_password`'s lockout check
(`is_locked_out`/`record_failed_attempt`/`record_successful_attempt`,
`backend/src/services/auth/lockout.py`) exists specifically because PR
#109's review found `current_password` checks are an unthrottled
brute-force oracle otherwise -- mirroring the endpoint without mirroring
this would reintroduce the exact gap that review already fixed once.
`RealInstructorAccount` has no `failed_login_attempts`/`locked_until`
columns today, so this feature adds both (see §2's table), mirroring
`RealGuardianAccount`'s shape exactly.

`lockout.py`'s three simple functions (`is_locked_out`,
`seconds_until_unlocked`, `record_successful_attempt`) only touch
`failed_login_attempts`/`locked_until` generically -- their type hints
widen to a new `AnyRealAccount = RealGuardianAccount |
RealInstructorAccount` alias, no behavior change. `record_failed_attempt`
is the one function genuinely coupled to a concrete model (`update
(RealGuardianAccount)...where(RealGuardianAccount.guardian_id ==
...)`, an atomic single-UPDATE race fix from the same PR #109 review)
-- rather than generalizing that `UPDATE` across two different primary-
key column names, add one sibling function,
`record_failed_attempt_instructor`, identical in shape but targeting
`RealInstructorAccount`/`instructor_id`. Matches this codebase's own
established precedent of small, duplicated, per-account-type functions
over a shared abstraction once the two models genuinely diverge (same
reasoning `register_instructor`/`register_guardian` already follow as
separate functions).

**Alternatives considered**: A single shared `change_password` helper
parameterized over account type -- rejected for this pass: the guardian
and instructor account rows aren't the same SQLAlchemy model, so a
shared helper would need the same per-model `UPDATE`-statement
branching `record_failed_attempt_instructor` already isolates; keeping
two small functions is the smaller, more boring diff.

**Gate**: Both `current_instructor`'s possible resolved types
(`RealInstructorAccount | DemoInstructorProfile`, `backend/src/
services/auth/dependencies.py`) reach this endpoint today. Only a
`RealInstructorAccount` has a `password_hash` to change; a demo session
MUST be rejected (`ForbiddenError`), matching spec.md FR-012's "password
change unavailable for a demo account."

## 2. Instructor display/notification/classroom-default preferences

**Decision**: Six new columns on `real_instructor_accounts`, mirroring
`RealGuardianAccount`'s existing `theme`/`larger_text`/`reduce_motion`
exactly (same types/defaults) plus three new ones this feature
introduces:

| Column | Type | Default | Notes |
|---|---|---|---|
| `theme` | `String` | `"system"` | Mirrors `RealGuardianAccount.theme`. |
| `larger_text` | `Boolean` | `false` | Mirrors `RealGuardianAccount.larger_text`. |
| `reduce_motion` | `Boolean` | `false` | Mirrors `RealGuardianAccount.reduce_motion`. |
| `notifications_enabled` | `Boolean` | `true` | New. Persisted only -- spec.md FR-008: no code path ever reads this to send anything. |
| `default_enrollment_mode` | `Enum(EnrollmentMode)` | `OPEN` | New. Pre-fills `CreateRosterIn.enrollment_mode` client-side only (spec.md FR-009). |
| `default_due_date_offset_days` | `Integer, nullable` | `NULL` | New. `NULL` = no due date; a positive integer = days added to the assignment's creation date, client-side only (spec.md FR-009/Clarifications). |

One PATCH endpoint change: extend the existing `InstructorMeIn`/
`InstructorMeOut` (`PATCH /api/auth/instructor/me`) with all six fields
as optional (`exclude_unset` semantics, same as `GuardianMeIn`), plus
extend `WhoAmIOut` with the same instructor-only optional fields the
guardian branch already has (`_INSTRUCTOR_ONLY_FIELDS`, mirroring the
existing `_GUARDIAN_ONLY_FIELDS` list) so `AccountDisplayPreferences.tsx`
can read them for an instructor session too.

**Rationale**: `GuardianMeIn`/`GuardianMeOut`/`update_guardian_me`
already established this exact flat-columns-on-the-account-row pattern
(spec 041) -- reusing it keeps Settings' save behavior identical in
shape to the guardian Settings page already shipped, and avoids a new
preferences table for six scalar values.

**Gate**: Same demo-account gate as §1 -- any of these six fields in
a PATCH body MUST be rejected (`ForbiddenError`) when the session is a
`DemoInstructorProfile`, which has none of these columns at all. A
`display_name`-only PATCH (today's only field) keeps working for a
demo instructor exactly as it does today.

**Alternatives considered**: A separate `instructor_preferences` table
-- rejected, same reasoning `RealGuardianAccount`'s own docstring
already gives for its own six fields: flat columns are simpler for a
fixed, small, 1:1-with-account set of scalars, and this feature's
`FR-013` deliberately bounds new schema surface to exactly this.

## 3. Frontend: generalizing `AccountDisplayPreferences`

**Decision**: Change `AccountDisplayPreferences.tsx`'s `refresh()` to
branch on `result.account_type === "guardian" || result.account_type
=== "instructor"` (both read the same `theme`/`larger_text`/
`reduce_motion` field names from `WhoAmIOut`), rather than
guardian-only.

**Rationale**: Per §2, the field names are identical on both account
types -- the component's existing logic needs only a one-line condition
change, not a rewrite.

## 4. Deletion-request entry points (Settings' Privacy section)

**Decision**: Zero backend change. Settings' "request a learner's data
be deleted" and "delete my instructor account" actions both call the
existing `POST /api/deletion-requests` (`backend/src/api/routes/
deletion.py`) with `target_type=LEARNER`/`target_type=INSTRUCTOR`
respectively -- `can_request_deletion` (`backend/src/services/
deletion/authorization.py`) already authorizes exactly these two cases
for an instructor session (self, or a learner enrolled in one of the
instructor's own rosters), confirmed by direct code read, not assumed.

**Rationale**: Directly satisfies spec.md FR-011's "no new deletion
rule." The learner picker (frontend-only) MUST source its options from
`GET /api/rosters/{roster_id}/enrollments` across the instructor's own
rosters -- never a new backend query -- so a learner not actually
enrolled in one of this instructor's rosters can never even appear as
pickable (the backend `can_request_deletion` check remains the real
enforcement either way).

## 5. The default instructor account and its per-subject rosters

**Decision**: A new `backend/src/services/roster/default_instructor.py`
module with two functions:

- `get_default_instructor(db: Session) -> RealInstructorAccount | None`
  -- looks up `RealInstructorAccount` by the normalized email in
  `DEFAULT_INSTRUCTOR_EMAIL` (same `_normalize_email` helper
  `auth.py` already has). Returns `None` if the env var is unset or no
  matching row exists yet (never raises) -- callers decide what that
  means for them (see `ensure_default_instructor_roster_for_subject`
  below).
- `ensure_default_instructor_roster_for_subject(db: Session, subject_id:
  str) -> None` -- no-ops (with a log line) if `get_default_instructor`
  returns `None`; otherwise checks for an existing `ClassroomRoster`
  with that `(instructor_id, subject_id)` pair and, if absent, calls
  the existing `create_roster()` service
  (`backend/src/services/roster/enrollment.py`) with
  `enrollment_mode=EnrollmentMode.OPEN`, then the existing
  `update_roster()`/`_apply_roster_is_listed` path to set
  `is_listed=True` (which requires `instructor_display_name` to be
  truthy -- satisfied because the seed script below always sets one).

A new script, `backend/scripts/seed_default_instructor.py`, mirroring
`seed_demo_instructor.py`'s idempotent shape exactly: reads
`DEFAULT_INSTRUCTOR_EMAIL`/`DEFAULT_INSTRUCTOR_PASSWORD`/an optional
`DEFAULT_INSTRUCTOR_DISPLAY_NAME` (default `"Cognivo"`) from the
environment, upserts the `RealInstructorAccount` row by email
(hashing the password via the existing `hash_password`, same as
`register_instructor` -- never re-hashing or overwriting the password
of an already-existing row, so a later operator-driven password change
via §1's endpoint is never silently reverted by re-running this script,
per spec.md FR-020), sets `is_demo=False` explicitly (Constitution
Principle VIII) and `display_name` from the env var/default, then
calls `ensure_default_instructor_roster_for_subject` for every `Subject`
row currently in the database.

`backend/scripts/load_content_artifact.py` gets one new call,
`ensure_default_instructor_roster_for_subject(db, subject.subject_id)`,
immediately after `persist_content_artifact` -- so adding a new subject
to the catalog (spec 040's pattern) keeps this always-true with zero
subject-specific code (Constitution Principle III), satisfying spec.md
FR-016. Because `get_default_instructor` no-ops cleanly when the env
var is unset, this change is a complete no-op for any environment
(e.g. a developer's local DB, CI) that hasn't seeded a default
instructor at all -- existing content-loading flows and tests are
unaffected.

**Rationale**: Reuses `create_roster()`/`update_roster()` completely
unchanged -- the default instructor's rosters are ordinary
`ClassroomRoster` rows with no new column, no new state, discovered by
the guardian class directory (`GET /api/rosters/directory`, spec 041)
through the exact same query that already joins `ClassroomRoster` to
`RealInstructorAccount` and filters `is_listed=True, enrollment_mode=
OPEN` -- confirmed by direct code read
(`backend/src/api/routes/rosters.py`'s `roster_directory_route`) that
this requires **zero code change** to list a default-instructor roster
once it exists. This is the concrete basis for spec.md FR-015's "no
special-casing beyond always existing."

**Alternatives considered**: A dedicated `is_default_instructor` flag
on `RealInstructorAccount` -- rejected as unnecessary schema: resolving
by the already-unique, already-indexed `email` column via one lookup
per guardian-assignment request (§6) is cheap and needs no new column,
keeping FR-013's bounded-schema promise tighter.

## 6. Guardian-facing quiz assignment, scoped to the default instructor

**Decision**: A new route, `POST /api/learners/{learner_id}/rosters/
{roster_id}/assignments`, guardian-authenticated
(`current_guardian`), with body `{topic_ids, question_count, due_at}`
(no `learner_ids` field -- the path's `learner_id` is the sole target,
unlike the instructor-side endpoint's `"all" | list[UUID]`). Checks, in
order: (a) the learner belongs to this guardian
(`learner.guardian_id == guardian.guardian_id`, same check
`list_learner_enrollments_route` already uses); (b) the learner is
enrolled in `roster_id` (`Enrollment` row exists); (c) `roster.
instructor_id == get_default_instructor(db).instructor_id` (§5) --
any failure raises `ForbiddenError`/`NotFoundError` per this project's
existing error-shape conventions. On success, calls the existing
`create_assignment()` service (`backend/src/services/quiz_assignment/
assignment.py`) unchanged, passing `instructor_id=roster.instructor_id`
(the default instructor's own id, so the resulting `QuizAssignment`
row and its `QUIZ_ASSIGNMENT_CREATED` audit event look identical to one
an instructor created directly) and `learner_ids=[learner_id]`.

Additive field on the existing `GET /api/learners/{learner_id}/
enrollments` response (`LearnerEnrollmentOut`): `is_default_instructor_
roster: bool`, computed by comparing each row's `instructor_id`
against `get_default_instructor(db)`'s id -- so the guardian frontend
knows exactly which enrollment card should show the new "assign a
quiz" action, without a second round-trip.

**Rationale**: Reuses `create_assignment()` entirely unchanged (same
audit shape, Constitution Principle V) -- the only genuinely new code
is the three-part authorization check above, which is exactly what
spec.md FR-017 requires and nothing more. Scoping to one `learner_id`
in the path (rather than reusing the instructor-side endpoint's
`roster_id`-rooted shape with a `learner_ids` list) matches how every
other guardian-facing endpoint in this codebase is already shaped
(`GET /api/learners/{learner_id}/enrollments` itself, `GET /api/
learners/{learner_id}/mastery-state`, etc.) -- a guardian's view of the
world is always rooted at "my learner," never at a roster they don't
own.

**Alternatives considered**: Letting a guardian call the existing
instructor-side `POST /api/rosters/{roster_id}/assignments` directly,
gated by a guardian-aware variant of `_get_owned_roster` -- rejected:
that endpoint's `instructor: InstructorAccount = Depends(current_
instructor)` dependency means a guardian session can't satisfy it at
all without changing its auth dependency, which would then require
every other call site reasoning about that endpoint to also account
for a guardian caller. A new, narrowly-scoped route keeps the blast
radius to exactly the one new capability.

## 7. Migration

**Decision**: One new Alembic migration adding all eight columns from
§1/§2 to `real_instructor_accounts`, all with server defaults (so it's
backward-compatible with every existing row) -- no data migration, no
backfill script needed (defaults apply at the DB level per
`server_default=`, same pattern every prior migration in this table's
history already uses, e.g. `RealGuardianAccount`'s own columns).

A second, small follow-up migration (PR #111 review) adds `password_changed_at`
alone -- nullable, no `server_default`, mirroring `RealGuardianAccount.
password_changed_at`'s own shape exactly: it must stay `NULL` for every
row until that row's first real password change, not backfilled to
`created_at` or any other value, or every session token issued before
this column existed would be retroactively invalidated the moment the
migration runs.
