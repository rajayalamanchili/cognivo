# API Contract Changes: Guardian & Public-Facing UI Redesign

New and changed backend routes only. Every route below follows this
codebase's existing conventions exactly (FastAPI `APIRouter`, Pydantic
request/response models, the existing `current_guardian`/`current_instructor`
dependencies, the existing `ForbiddenError`/`ConflictError`/`UnprocessableError`
error classes) -- no new pattern is introduced.

## `backend/src/api/routes/auth.py`

### `PATCH /api/auth/guardian/me`

Guardian-only (`current_guardian`). Updates any subset of: `name: str | None`,
`email: str | None`, `read_aloud_default: bool | None`, `larger_text: bool | None`,
`reduce_motion: bool | None`, `theme: Literal["system","light","dark"] | None`,
`quiz_finished_email_enabled: bool | None`, `weekly_summary_enabled: bool | None`.
All fields optional (only provided fields change). `email` goes through the
same `_normalize_email` + uniqueness check `register_guardian` already uses
-- `ConflictError("email_taken")` on collision. Returns the updated
`RealGuardianAccount`'s full current state (same shape `whoami` now also
returns for a guardian session, FR-009).

### `POST /api/auth/guardian/change-password`

Guardian-only. Body: `current_password: str`, `new_password: str` (`min_length=8`,
matching `AuthCredentialsIn`'s existing constraint). Verifies
`current_password` via the existing `verify_password`; `AuthenticationError`
on mismatch. Re-hashes `new_password` via the existing `hash_password`, and
sets `password_changed_at = now()` (Edge Cases/FR-022, research.md §6) so
every session token issued before this call is rejected on its next use.
204 on success -- no response body, matching `logout`'s existing 204 shape
for a side-effect-only action.

### `PATCH /api/auth/instructor/me`

Instructor-only (`current_instructor`). Body: `display_name: str` (required,
non-empty -- this is the only field this endpoint changes, per FR-017; email/
password changes for instructors are explicitly out of scope for this
feature). 200 with the updated `display_name`. This is the *only* way
`display_name` is ever set -- `POST /api/auth/instructor/register` is
unchanged and never collects it (research.md §3, revised during
`/speckit-analyze` to avoid a required-field break across every existing
instructor-registration call site).

### `GET /api/auth/whoami` (extended, not a new route)

`WhoAmIOut` gains optional fields, populated only when `account_type == "guardian"`:
`name: str | None`, `read_aloud_default: bool`, `larger_text: bool`,
`reduce_motion: bool`, `theme: str`, `quiz_finished_email_enabled: bool`,
`weekly_summary_enabled: bool`. `None`/omitted for every other account type,
same pattern `pending_deletion_warnings` already follows (populated only
for the relevant `account_type` branch).

## `backend/src/api/routes/mastery.py`

### `PATCH /api/learners/{learner_id}/practice-reminders-preference`

Mirrors the existing `career-connections-preference` endpoint's exact
shape (same file). Body: `enabled: bool`. Gated by
`require_learner_ownership_if_real` (guardian-only for a real learner;
unauthenticated for the demo learner, same as `career-connections-
preference`'s own documented precedent). Toggles
`LearnerProfile.practice_reminders_enabled` (FR-011 -- the one
per-learner, not per-guardian, toggle). Returns the new state.

## `backend/src/api/routes/learners.py`

### `GET /api/learners/mine`

Guardian-only (`current_guardian`). Added during `/speckit-analyze`
(FR-023) -- no existing endpoint returns a guardian's full learner set;
`addedLearners` on Guardian · My learners is session-only client state
today. No request body. Returns every `LearnerProfile` where
`guardian_id` matches the calling guardian, each with: `learner_id: UUID`,
`display_name: str`, `enrollment: {roster_id: UUID, subject_id: str,
grade: int | None} | null` (left-joined through the existing `Enrollment`
→ `ClassroomRoster` relationship, `null` when the learner isn't
currently enrolled anywhere). No pagination -- bounded by one guardian's
own learner count.

## `backend/src/api/routes/rosters.py`

### `GET /api/rosters/directory`

Guardian-only (`current_guardian`, same dependency `join_roster_route`
already uses). No request body. Returns every `ClassroomRoster` where
`is_listed = true AND enrollment_mode = 'open'`, each with:
`roster_id: UUID`, `subject_id: str`, `grade: int | None`,
`instructor_display_name: str`, `join_code: str` (non-secret once listed,
per `research.md` §3). No pagination -- directory size is bounded by how
many instructors have opted a roster in, not expected to need it at this
feature's scale.

### `PATCH /api/rosters/{roster_id}` (extended, not a new route)

`UpdateRosterIn` gains `is_listed: bool | None` (optional, alongside the
existing `enrollment_mode`). Setting `is_listed=True` while
`enrollment_mode` (existing or newly-provided in the same request)
resolves to `CLOSED`, or while the owning instructor's `display_name` is
`NULL`, raises `UnprocessableError` (new error codes:
`"cannot_list_closed_roster"`, `"instructor_display_name_required"`).
Setting `enrollment_mode=CLOSED` while the roster is currently listed
clears `is_listed` to `False` as a side effect, rather than erroring --
the instructor is closing the roster, which this project treats as an
implicit "stop listing it" rather than a separate required step.

## Existing routes, unchanged behavior, reused as-is

- `POST /api/rosters/join` -- the directory's "join" action calls this
  existing route with the `join_code` the directory response already
  provided (`research.md` §3) -- no new request/response shape.
- `GET /api/learners/{learner_id}/mastery-state`, `GET /api/learners/{learner_id}/activity-summary`,
  `GET /api/learners/{learner_id}/recommendations` (or `topic-priority-preview`),
  `GET /api/learners/{learner_id}/next-question`, and the Tutor Agent's
  existing conversational endpoint -- all already gated by
  `require_learner_ownership_if_real`; the real-learner session (FR-016)
  calls each with the guardian's own real `learner_id` instead of the
  demo learner's. No request/response shape changes to any of these.
- `POST /api/deletion-requests`, `GET /api/deletion-requests` (spec 020) --
  Settings' Privacy & data section (FR-012) wires existing UI to these
  exactly as they are today.
