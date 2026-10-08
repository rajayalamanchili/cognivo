# Phase 1 Data Model: Instructor-Facing UI Redesign and Default-Instructor Self-Service

No new tables. One existing table extended; no change to any other
entity's shape (`ClassroomRoster`, `Enrollment`, `QuizAssignment`,
`DeletionRequest`, `Subject` are all reused exactly as they exist
today).

## `RealInstructorAccount` (extended)

Existing table `real_instructor_accounts`
(`backend/src/models/real_instructor_account.py`). New columns:

| Column | Type | Nullable | Default | Added by |
|---|---|---|---|---|
| `theme` | `String` | No | `"system"` | FR-007 |
| `larger_text` | `Boolean` | No | `false` | FR-007 |
| `reduce_motion` | `Boolean` | No | `false` | FR-007 |
| `notifications_enabled` | `Boolean` | No | `true` | FR-008 |
| `default_enrollment_mode` | `Enum(EnrollmentMode)` (reuses the existing `enrollment_mode` Postgres enum type -- no new enum) | No | `OPEN` | FR-009 |
| `default_due_date_offset_days` | `Integer` | **Yes** | `NULL` | FR-009 |
| `failed_login_attempts` | `Integer` | No | `0` | FR-006 (mirrors `RealGuardianAccount`'s lockout column, research.md §1) |
| `locked_until` | `DateTime(timezone=True)` | **Yes** | `NULL` | FR-006 (mirrors `RealGuardianAccount`'s lockout column, research.md §1) |

**Validation rules**:

- `theme` MUST be one of `"system" | "light" | "dark"` (mirrors
  `GuardianMeIn.theme`'s `Literal` type) -- enforced at the Pydantic
  request-model level, same as the guardian side.
- `default_due_date_offset_days`, when not `NULL`, MUST be a positive
  integer (`> 0`) -- enforced at the Pydantic level (`Field(gt=0)` on
  the optional field). `NULL` is the only representation of "no due
  date by default" (spec.md's Clarifications, second pass).
- No new uniqueness or foreign-key constraint; all eight columns are
  independent, per-row scalars.

**State/lifecycle**: Six of the eight are never referenced by any other
table's logic -- they are read only to pre-fill a frontend form
(`default_enrollment_mode`/`default_due_date_offset_days`) or applied
directly to the document root
(`theme`/`larger_text`/`reduce_motion`, exactly as
`AccountDisplayPreferences.tsx` already does for a guardian) or never
read by any code path at all (`notifications_enabled`, FR-008). The
remaining two (`failed_login_attempts`/`locked_until`) are the one
exception -- read and written by `backend/src/services/auth/
lockout.py`'s functions on every password-change attempt (research.md
§1), the same way `RealGuardianAccount`'s identical columns already
are. None of the eight require a cascade or cleanup on
`DeletionRequest` execution beyond what already deletes the whole
`RealInstructorAccount` row today.

## The default instructor (no new entity)

A `RealInstructorAccount` row like any other, distinguished only by
its `email` matching the `DEFAULT_INSTRUCTOR_EMAIL` environment
variable at lookup time (`get_default_instructor`, research.md §5) --
not a new column, not a new table, not a new enum value. `is_demo`
MUST be `false` on this row (FR-019); `display_name` MUST be non-empty
(required for `is_listed=True`, already an existing invariant on
`ClassroomRoster` via `_apply_roster_is_listed`).

Its per-subject rosters are ordinary `ClassroomRoster` rows
(`enrollment_mode=OPEN`, `is_listed=true`, `grade=NULL` -- deliberately
unrestricted by grade, since this fallback is meant to serve any
learner regardless of grade band) with `instructor_id` set to this
account's `instructor_id`, created via the existing `create_roster()`/
`update_roster()` services, one per `Subject.subject_id` (FR-014).

**Identity/uniqueness**: At most one default-instructor-owned
`ClassroomRoster` per `(instructor_id, subject_id)` pair -- enforced at
the application level by `ensure_default_instructor_roster_for_subject`
checking for an existing row before creating one (idempotency, not a
new DB constraint; `ClassroomRoster` has no unique constraint on
`(instructor_id, subject_id)` today and this feature does not add one,
since a real instructor is still allowed multiple rosters per subject
-- only the default-instructor seeding path enforces "at most one" for
itself).

## Guardian-facing quiz assignment (no new entity)

Reuses `QuizAssignment`/`QuizAssignmentTarget` exactly as they exist
today (`backend/src/models/quiz_assignment.py`,
`quiz_assignment_target.py`) -- a row created this way is
indistinguishable in storage from one an instructor created directly;
`instructor_id` on the resulting `QuizAssignment` row is the default
instructor's id either way (research.md §6).

## `GET /api/learners/{learner_id}/enrollments` response (additive field)

`LearnerEnrollmentOut` (`backend/src/api/routes/rosters.py`) gains one
new, read-only field:

| Field | Type | Meaning |
|---|---|---|
| `is_default_instructor_roster` | `bool` | `true` when this enrollment's roster is owned by the default instructor (research.md §6) -- tells the guardian frontend which enrollment card gets the new "assign a quiz" action. |

No existing field removed or retyped; every existing consumer of this
response is unaffected by the addition (Pydantic models ignore unknown
fields on the client side by default, and no existing frontend code
destructures this response exhaustively in a way that would break on
an extra key).
