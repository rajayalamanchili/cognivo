# Data Model: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review

**Feature**: `010-instructor-classroom` | **Date**: 2026-08-23

## Correction to spec 009's forward-looking data model

Spec 009's `data-model.md` proposed a separate `RealLearnerAccount`
table. Building against it during this plan surfaced a real
incompatibility: `AssessmentEvent.learner_id`, `MasteryState.learner_id`,
`QuizSession.learner_id`, and both of `GeneratedQuestion`'s learner-
referencing columns (`learner_id`, `flagged_by`) are all hard foreign
keys to `demo_learner_profiles.learner_id` specifically -- a separate
`RealLearnerAccount` table could never be referenced by any of them
without migrating all five FK constraints.

**Corrected design**: no separate real-learner table. `demo_learner_profiles`
is renamed to `learner_profiles` (model class `DemoLearnerProfile` ->
`LearnerProfile`) and gains two new nullable columns:

- `guardian_id` (FK -> `real_guardian_accounts.guardian_id`, nullable)
- `retention_record_id` (FK -> `retention_records.retention_record_id`,
  nullable)

A demo row (`is_demo: true`) leaves both null, exactly as today. A real
row (`is_demo: false`) sets both non-null -- `RetentionRecord`'s
existence becomes the enforcement mechanism for spec 009's SC-004 ("no
account can be created without one"), via a `NOT NULL` constraint
scoped by application logic at creation time (a DB-level `CHECK`
tying nullability to `is_demo` was considered and rejected: SQLAlchemy/
Postgres can express "nullable" or "not nullable," not "nullable
if-and-only-if column X is true," without a trigger -- application-
level enforcement plus an integration test is this codebase's existing
pattern for this class of invariant, e.g. `check_no_real_account_path.py`
itself is a static check, not a DB constraint).

This is a correction to already-merged content, not a reversal of
policy -- spec 009's actual requirements (guardian-held credentials,
open/closed enrollment, hard-delete, retention) are unchanged; only the
*table shape* implementing them changes. Renaming now, before any real
(non-demo) row has ever existed (spec 009's own gate confirms this),
is the cheapest point in this project's lifetime to make this
correction -- every later point would mean migrating live real data
instead of only synthetic rows.

## Entities

### LearnerProfile (renamed from `DemoLearnerProfile`)

| Field | Type | Notes |
|---|---|---|
| `learner_id` | UUID, PK | Unchanged -- every existing FK relationship continues to point here, just at the renamed table. |
| `display_name` | string, not null | Unchanged. |
| `is_demo` | boolean, not null | Unchanged -- still the authoritative discriminator `check_no_real_account_path.py` checks for. |
| `guardian_id` | FK -> `RealGuardianAccount.guardian_id`, nullable | **NEW**. Null for a demo row; the credential holder (spec 009 FR-003) for a real row. |
| `retention_record_id` | FK -> `RetentionRecord.retention_record_id`, nullable | **NEW**. Null for a demo row; required non-null for a real row (enforced at creation time, not a DB constraint -- see above). |
| `created_at` | timestamp, not null | Unchanged. |

### RealGuardianAccount

| Field | Type | Notes |
|---|---|---|
| `guardian_id` | UUID, PK | |
| `email` | string, unique, not null | Unique within this table only (research.md §2) -- not globally unique across `RealInstructorAccount`. |
| `password_hash` | string, not null | Argon2id (research.md §1). |
| `created_at` | timestamp, not null | |
| `is_demo` | boolean, not null | Always `false` -- present so `check_no_real_account_path.py` needs no special-case exemption. |

### RealInstructorAccount

| Field | Type | Notes |
|---|---|---|
| `instructor_id` | UUID, PK | |
| `email` | string, unique, not null | Unique within this table only (research.md §2). |
| `password_hash` | string, not null | Argon2id. |
| `is_demo` | boolean, not null | Always `false`. |
| `created_at` | timestamp, not null | |

### ClassroomRoster

| Field | Type | Notes |
|---|---|---|
| `roster_id` | UUID, PK | |
| `instructor_id` | FK -> `RealInstructorAccount.instructor_id`, not null | One owning instructor per roster (co-taught rosters are a future need, not required here). |
| `subject_id` | FK -> `Subject.subject_id`, not null | **Fills the gap spec 009 left undetermined** -- a roster is scoped to exactly one subject (spec.md's Assumption), matching how `build_weak_area_report` and this platform's content model are already per-subject. |
| `enrollment_mode` | enum(`open`, `closed`), not null | FR-004/FR-005/FR-006. Mutable after creation (an instructor can toggle it; no special transition logic beyond updating the column). |
| `join_code` | string, nullable | Meaningful only when `enrollment_mode = open`. |
| `created_at` | timestamp, not null | |

### Enrollment

| Field | Type | Notes |
|---|---|---|
| `enrollment_id` | UUID, PK | |
| `learner_id` | FK -> `LearnerProfile.learner_id`, not null | |
| `roster_id` | FK -> `ClassroomRoster.roster_id`, not null | Unique together with `learner_id` -- a learner enrolls in a given roster at most once at a time (re-enrolling after an unenrollment creates a new row). |
| `enrolled_at` | timestamp, not null | |
| `authorized_by_type` | enum(`guardian`, `instructor`), not null | FR-011/spec 009 FR-011 -- guardian for an open join, instructor for a closed approval. |
| `authorized_by_id` | UUID, not null | The specific guardian or instructor identity. |

Deleting an `Enrollment` row *is* unenrollment (FR-007a) -- no soft-delete
or status column; the row's existence is the enrollment's existence.

### EnrollmentRequest

| Field | Type | Notes |
|---|---|---|
| `enrollment_request_id` | UUID, PK | |
| `learner_id` | FK -> `LearnerProfile.learner_id`, not null | |
| `roster_id` | FK -> `ClassroomRoster.roster_id`, not null | Only created for a `closed` roster's join attempt (FR-006). |
| `requested_at` | timestamp, not null | |
| `decided_at` | timestamp, nullable | Null while pending. |
| `decision` | enum(`approved`, `declined`), nullable | Null while pending. On `approved`, an `Enrollment` row is created in the same transaction. |

A second join attempt while a request is already pending for that
(`learner_id`, `roster_id`) pair returns the existing pending request
rather than creating a duplicate (Edge Cases).

### DeletionRequest (from spec 009, unchanged)

| Field | Type | Notes |
|---|---|---|
| `deletion_request_id` | UUID, PK | |
| `target_type` | enum(`learner`, `instructor`, `guardian`), not null | |
| `target_id` | UUID, not null | Not a FK (spec 009: the target row is gone by completion). |
| `requested_by` | string, not null | |
| `requested_at` | timestamp, not null | |
| `completed_at` | timestamp, nullable | |

Unenrollment (FR-007a) never creates a `DeletionRequest` -- it only
removes an `Enrollment` row. A `DeletionRequest` targeting a `learner`
does cascade to remove that learner's `Enrollment`/`EnrollmentRequest`
rows too, as one item in spec 009 FR-005's full cascade.

### RetentionRecord (from spec 009, unchanged)

| Field | Type | Notes |
|---|---|---|
| `retention_record_id` | UUID, PK | |
| `account_type` | enum(`learner`, `instructor`), not null | |
| `account_id` | UUID, not null | |
| `authorized_by_type` | enum(`guardian`, `instructor`), not null | |
| `authorized_by_id` | UUID, not null | |
| `enrollment_status` | enum(`active`, `inactive`), not null | |
| `became_inactive_at` | timestamp, nullable | |

### DemoInstructorProfile

| Field | Type | Notes |
|---|---|---|
| `instructor_id` | UUID, PK | |
| `display_name` | string, not null | |
| `is_demo` | boolean, not null | Always `true` -- structurally parallel to `LearnerProfile`'s demo rows, kept as its own table (mirroring the pre-existing separation between `LearnerProfile` and the new `RealInstructorAccount`) rather than a nullable-`is_demo` row inside `RealInstructorAccount`, so a demo instructor never needs a password/credential at all. |
| `created_at` | timestamp, not null | |

## State transitions

`EnrollmentRequest`: `requested_at` set, `decision` null (pending) ->
instructor approves (creates `Enrollment`, sets `decision: approved`,
`decided_at`) or declines (`decision: declined`, `decided_at`, no
`Enrollment` created). Terminal either way -- a declined request doesn't
transition further; a new join attempt creates a new request.

`Enrollment`: created (join or approval) -> deleted (unenrollment,
FR-007a, or cascaded by a `DeletionRequest` targeting the learner).

`GeneratedQuestion.validation_status` (existing enum, unchanged shape):
`flagged` -> `valid` (instructor reactivates) or stays `flagged`
permanently (instructor rejects -- no further state; `flagged` already
excludes it from future selection, per Milestone 1's existing
behavior). FR-012/FR-013 add an audited event recording which
resolution occurred; they do not add a new `validation_status` value.
