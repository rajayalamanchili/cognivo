# Data Model: Privacy & Retention Spec -- the Real Learner Data Gate

**Feature**: `009-privacy-retention` | **Date**: 2026-08-22

None of the entities below are persisted by this spec (research.md
§4) -- no migration ships with this feature. This is the forward-
looking schema Milestone 7 proper's own `plan.md` must implement
against, concretizing spec.md's Key Entities section one level deeper
(fields, types, relationships) so that future plan doesn't have to
re-derive this spec's requirements into a schema from scratch.

## RealGuardianAccount

The actual authenticating identity (FR-003) -- a parent/guardian, never
the learner.

| Field | Type | Notes |
|---|---|---|
| `guardian_id` | UUID, PK | |
| `email` | string, unique, not null | Login identifier; also the channel for deletion-request confirmation (FR-004). |
| `password_hash` | string, not null | Never a plaintext credential; standard hashing, no new decision needed beyond this project's existing auth conventions once Milestone 7 proper picks one. |
| `created_at` | timestamp, not null | |
| `is_demo` | boolean, not null | Always `false` for a `RealGuardianAccount` by definition -- a demo learner has no guardian account at all (Milestone 1's `DemoLearnerProfile` pattern continues unchanged). Present so the gate script (research.md §1) doesn't need a special-case exemption for this table. |

## RealLearnerAccount

**Corrected 2026-08-23 by `specs/010-instructor-classroom/data-model.md`**:
this entity as a *separate table* turned out to be wrong -- building
against it during that spec's planning found that `AssessmentEvent`,
`MasteryState`, `QuizSession`, and `GeneratedQuestion`'s learner-
referencing columns are all hard foreign keys to
`demo_learner_profiles.learner_id` specifically, not a generalizable
"either table" relationship as this section originally claimed (see
the now-inaccurate note on the `learner_id` row below). The corrected
design extends `demo_learner_profiles` in place (renamed to
`learner_profiles`) with nullable `guardian_id`/`retention_record_id`
columns instead of creating a new table -- see spec 010's data-model.md
for the actual implemented shape. Left here, uncorrected below, as the
historical record of what this spec originally proposed; do not build
against this section.

A real student's profile (FR-003), linked to exactly one guardian.
Structurally parallel to `DemoLearnerProfile` for everything downstream
of enrollment (mastery state, assessment events, generated questions),
but with no login credential of its own.

| Field | Type | Notes |
|---|---|---|
| `learner_id` | UUID, PK | Same shape as `DemoLearnerProfile.learner_id` -- every existing FK relationship (`mastery_states`, `generated_questions`, `assessment_events`) generalizes to either table without a schema change to those tables themselves. |
| `guardian_id` | FK -> `RealGuardianAccount.guardian_id`, not null | The credential holder (FR-003) -- never null, never a second guardian per learner in v1 (a reasonable default; joint-guardian access is a plausible future need, not required by this spec). |
| `display_name` | string, not null | |
| `is_demo` | boolean, not null | Always `false`. |
| `created_at` | timestamp, not null | |
| `retention_record_id` | FK -> `RetentionRecord.retention_record_id`, not null | Enforces SC-004 ("no account can be created without one") at the schema level, not just as a process convention. |

## RealInstructorAccount

A real educator's account (Milestone 7 proper), owning one or more
`ClassroomRoster`s.

| Field | Type | Notes |
|---|---|---|
| `instructor_id` | UUID, PK | |
| `email` | string, unique, not null | |
| `password_hash` | string, not null | |
| `is_demo` | boolean, not null | Always `false`. |
| `created_at` | timestamp, not null | |

## ClassroomRoster

The enrollment boundary FR-006's access control is enforced against,
and the open/closed distinction from FR-003a.

| Field | Type | Notes |
|---|---|---|
| `roster_id` | UUID, PK | |
| `instructor_id` | FK -> `RealInstructorAccount.instructor_id`, not null | Exactly one owning instructor per roster in v1 -- co-taught classrooms are a plausible future need, not required here. |
| `enrollment_mode` | enum(`open`, `closed`), not null | FR-003a. `open`: a guardian may enroll their learner via `join_code` without instructor action. `closed`: enrollment requires an instructor-side approval/invite action (not modeled as a separate entity here -- Milestone 7 proper's own plan defines that workflow's shape; this spec only requires that the approval step exists and is recorded). |
| `join_code` | string, nullable | Only meaningful when `enrollment_mode = open`; null for closed rosters. |
| `created_at` | timestamp, not null | |

**Enrollment** (the membership linking a `RealLearnerAccount` to a
`ClassroomRoster`) is a many-to-many join, but is not modeled as its
own row here beyond noting it must exist -- its exact shape (e.g.
whether a learner can belong to more than one roster) is a Milestone 7
proper implementation detail this spec doesn't need to constrain
further than FR-006's access-control requirement already does.

## DeletionRequest

The audit record proving FR-004's 30-day SLA was met (Constitution
Principle V).

| Field | Type | Notes |
|---|---|---|
| `deletion_request_id` | UUID, PK | |
| `target_type` | enum(`learner`, `instructor`, `guardian`), not null | |
| `target_id` | UUID, not null | The `learner_id`/`instructor_id`/`guardian_id` being deleted. Not a foreign key -- by the time this row is queried after completion, the target row itself is gone (hard delete, per Clarifications). |
| `requested_by` | string, not null | Free-text identifier of who submitted the request (the guardian, the instructor, or "institution" for an institution-initiated request) -- not a FK, for the same reason `target_id` isn't: the requester's own account may itself be the thing being deleted. |
| `requested_at` | timestamp, not null | |
| `completed_at` | timestamp, nullable | Null while in progress. `completed_at - requested_at <= 30 days` is SC-002's measurable check. |

## RetentionRecord

Per-account metadata driving FR-010's post-inactivity auto-deletion and
FR-011's authorization audit trail.

| Field | Type | Notes |
|---|---|---|
| `retention_record_id` | UUID, PK | |
| `account_type` | enum(`learner`, `instructor`), not null | |
| `account_id` | UUID, not null | Mirrors `DeletionRequest.target_id`'s not-a-FK reasoning. |
| `authorized_by_type` | enum(`guardian`, `instructor`), not null | FR-011: which party's action created this enrollment -- `guardian` for an open-classroom join, `instructor` for a closed-classroom approval. |
| `authorized_by_id` | UUID, not null | The specific guardian or instructor identity from `authorized_by_type`. |
| `enrollment_status` | enum(`active`, `inactive`), not null | Drives FR-010's 1-year post-inactivity clock. |
| `became_inactive_at` | timestamp, nullable | Null while `active`. `now() - became_inactive_at > 1 year` is FR-010's automatic-deletion trigger condition. |

## State transitions

`RetentionRecord.enrollment_status`: `active` -> `inactive` (e.g. end of
academic term with no successor enrollment, Milestone 7 proper's own
concern to detect) -> triggers FR-010's 1-year countdown -> automatic
hard-delete (same FR-004/FR-005 path a manual `DeletionRequest` uses) if
no explicit `DeletionRequest` arrives first.

`DeletionRequest`: `requested_at` set (in progress, `completed_at`
null) -> cascade delete across every table in FR-005's list -> `completed_at`
set. No other states -- there is no "denied" or "partial" state by
design (FR-004 is unconditional once a legitimate requester is
verified; verifying the requester's identity is Milestone 7 proper's
auth concern, not this spec's).
