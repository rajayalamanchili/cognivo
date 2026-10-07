# Phase 1 Data Model: Guardian & Public-Facing UI Redesign

No new table. Every addition below is a new column on an existing entity,
per `research.md` §2-3's decisions. One new migration covers all of them.

## `RealGuardianAccount` (existing table: `real_guardian_accounts`)

| Column | Type | Default | Notes |
|---|---|---|---|
| `name` | `str \| None` | `NULL` | New (FR-009). Nullable -- no existing guardian has ever set one; the Settings Account section is where it's first entered, not required at registration (same as `RealInstructorAccount.display_name` below, which is likewise optional at registration but enforced at a different point -- roster-listing time, not registration). |
| `read_aloud_default` | `bool` | `False` | New (FR-011). Guardian-wide, matching the mockup's unkeyed toggle row. |
| `larger_text` | `bool` | `False` | New (FR-011). |
| `reduce_motion` | `bool` | `False` | New (FR-011). |
| `theme` | `str` | `'system'` | New (FR-011). One of `'system' \| 'light' \| 'dark'`, validated at the API layer (Pydantic `Literal`), not a DB enum type -- consistent with this column being a simple, low-cardinality string rather than needing a Postgres enum migration. |
| `quiz_finished_email_enabled` | `bool` | `True` | New (FR-011). Defaults on, matching the mockup's own default state. |
| `weekly_summary_enabled` | `bool` | `False` | New (FR-011). Defaults off, matching the mockup. |
| `password_changed_at` | `datetime \| None` | `NULL` | New (Edge Cases/FR-022, added during `/speckit-analyze`). Set to `now()` on every successful `POST /api/auth/guardian/change-password` call. `NULL` for an account that has never changed its password since this column was added -- `current_guardian` only rejects a session token when this is non-`NULL` *and* newer than the token's own `iat` (research.md §6), so a never-changed account's existing sessions are unaffected. |

No change to `guardian_id`, `email`, `password_hash`, `is_demo`,
`created_at` -- all pre-existing.

## `RealInstructorAccount` (existing table: `real_instructor_accounts`)

| Column | Type | Default | Notes |
|---|---|---|---|
| `display_name` | `str \| None` | `NULL` | New (FR-017). Nullable at the DB level and never required at registration (`register_instructor` is unchanged -- revised during `/speckit-analyze`, research.md §3, to avoid breaking every existing instructor-registration call site for a requirement that only needs to hold at listing time). A `NULL`-display-name instructor -- new or pre-existing, no distinction -- is blocked from setting `is_listed=True` on any roster until they set one via `PATCH /api/auth/instructor/me` (Edge Cases), enforced in the directory-listing code path, not a DB constraint. |

## `LearnerProfile` (existing table: `learner_profiles`)

| Column | Type | Default | Notes |
|---|---|---|---|
| `practice_reminders_enabled` | `bool` | `False` | New (FR-011). The one per-learner (not per-guardian) notification toggle the mockup shows (`"Practice reminders for Eli"`) -- mirrors the existing `career_connections_enabled` column's exact shape and precedent on this same table. |

## `ClassroomRoster` (existing table: `classroom_rosters`)

| Column | Type | Default | Notes |
|---|---|---|---|
| `is_listed` | `bool` | `False` | New (FR-018). Application-level invariant (not a DB CHECK constraint, same precedent `LearnerProfile`'s own docstring already documents for a structurally identical case): MUST NOT be `True` when `enrollment_mode = CLOSED`. Enforced in `services/roster/enrollment.py` at the same call site that already changes `enrollment_mode`. |

## Relationships

No new foreign key, no new relationship. Every new column belongs to an
entity that already exists and is already related to everything it needs
to be (a `ClassroomRoster` already has `instructor_id`; the directory
query (`research.md` §3) is a plain join on that existing FK to read the
instructor's new `display_name`). `GET /api/learners/mine` (FR-023,
research.md §5) is the same shape: a plain query on `LearnerProfile.
guardian_id`, left-joined through the pre-existing `Enrollment` →
`ClassroomRoster` relationship -- no new FK either.

## Validation rules

- `RealGuardianAccount.email` uniqueness: unchanged, pre-existing (case-insensitive, per `auth.py`'s `_normalize_email`). The new `PATCH /api/auth/guardian/me` email-change path reuses the exact same conflict-check pattern `register_guardian` already uses.
- `RealGuardianAccount.theme`: validated as `Literal["system", "light", "dark"]` at the Pydantic request-model layer; an out-of-range value is a 422, never silently coerced.
- `ClassroomRoster.is_listed` / `enrollment_mode` mutual exclusion: enforced in `services/roster/enrollment.py`, not the database -- a request that would produce the invalid combination (setting `is_listed=True` on a closed roster, or setting `enrollment_mode=CLOSED` on a listed roster without also clearing `is_listed`) is rejected with a 422, mirroring this project's existing `UnprocessableError` pattern (e.g. `_check_grade_matches_subject` in the same file).
- `RealInstructorAccount.display_name` required for listing: enforced in the same `is_listed`-setting code path above -- attempting to set `is_listed=True` while `display_name IS NULL` raises the same `UnprocessableError` class, not a separate check.

## State transitions

None introduced. `ClassroomRoster.enrollment_mode`'s existing
open/closed transition (`update_roster_enrollment_mode`) gains one new
side effect (clearing `is_listed` when transitioning to closed) but no
new state machine.
