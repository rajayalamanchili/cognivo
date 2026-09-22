# Data Model: Real-Account Deletion Pathway

**Feature**: `020-deletion-pathway` | **Date**: 2026-09-21 (updated
2026-09-21 for the FR-011 pre-deletion-warning clarification)

No new tables. This feature makes two already-modeled entities
(`DeletionRequest`, `RetentionRecord`, both from spec 009) do real work
for the first time, defines the cascade order across tables that
already exist, and adds one new nullable column to `RetentionRecord`
to support FR-011's warning (research.md R10).

## Existing entities this feature acts on

### DeletionRequest (`backend/src/models/deletion_request.py`, unchanged)

| Field | Meaning for this feature |
|---|---|
| `deletion_request_id` | Unchanged. |
| `target_type` | `learner` \| `instructor` \| `guardian` -- selects which cascade-order table below applies. |
| `target_id` | Unchanged; still deliberately not a FK (the row it names is gone once processing completes). |
| `requested_by` | Read by `GET /api/deletion-requests/{id}` to authorize who may check status (FR-009). |
| `requested_at` | Read by the cron executor to process oldest-first. |
| `completed_at` | `NULL` = pending, set once the full cascade for this request has committed. This is the field this feature finally makes real -- previously nothing ever set it. |

### RetentionRecord (`backend/src/models/retention_record.py`, +1 column: `inactivity_warning_sent_at`)

| Field | Meaning for this feature |
|---|---|
| `account_type` | `learner` \| `instructor` -- note guardians have no `RetentionRecord` row; a guardian's deletion is never inactivity-triggered directly (R4/R8 in research.md), only cascaded from their learners or requested explicitly. |
| `account_id` | The learner or instructor this record tracks. |
| `enrollment_status` | `active` \| `inactive`. |
| `became_inactive_at` | The inactivity sweep (FR-005) compares this against "now - 1 year" (spec 009 FR-010). `NULL` or `enrollment_status = active` means never swept. |
| `inactivity_warning_sent_at` **(NEW, nullable `DateTime`)** | Reconciled by the sweep on every run as two mutually exclusive, ordered checks (FR-011, research.md R10): **(1)** if `enrollment_status = "active"`, clear to `NULL` (Acceptance Scenario 3) -- checked first, regardless of what `became_inactive_at` still holds; **(2)** else, if `enrollment_status = "inactive"` and still `NULL`, set to `now()` once inactivity age crosses `became_inactive_at + (1 year - 7 days)`. The `enrollment_status = "inactive"` guard on (2) is required -- `became_inactive_at` can be stale-but-non-null on an already-reactivated record, so the threshold arithmetic alone isn't a safe trigger. Read by `GET /api/auth/whoami` (research.md R9) to populate `pending_deletion_warnings`. |

## Deletion cascade order

Each list is deepest-dependency-first: a row lower in the list is
deleted only after every row above it that references it is already
gone. All deletes for one target happen in a single DB transaction
(research.md R2).

### Target type: `learner`

| # | Table | Match | Note |
|---|---|---|---|
| 1 | `tutor_exchanges` | via `tutoring_sessions.learner_id = target_id` (join through `session_id`) | Milestone 9 transcripts -- highest-sensitivity data in the cascade (spec 009 `data-classification.md`). |
| 2 | `tutoring_sessions` | `learner_id = target_id` | |
| 3 | `quiz_assignment_targets` | `learner_id = target_id` | Instructor-scheduling linkage row, not the learner's own quiz history. |
| 4 | `assessment_events` | `learner_id = target_id` | Audit-log rows -- deleted, not anonymized, per spec 009's hard-delete-only decision. |
| 5 | `generated_questions` | `learner_id = target_id` (owned questions) | Deleted outright. |
| 5a | `generated_questions.flagged_by` | `flagged_by = target_id` **AND** `learner_id != target_id` | `SET NULL`, not delete -- the question belongs to a different, still-active learner (research.md R2). |
| 6 | `mastery_states` | `learner_id = target_id` | |
| 7 | `enrollment_requests` | `learner_id = target_id` | |
| 8 | `enrollments` | `learner_id = target_id` | |
| 9 | `grade_progress` | `learner_id = target_id` | Milestone 17 table. |
| 10 | `quiz_sessions` | `learner_id = target_id` | Safe once #3 and #5 (which FK to `quiz_session_id`) are gone. |
| 11 | `learner_profiles` | `learner_id = target_id` | The identity row itself. |
| 12 | `retention_records` | `account_type = 'learner' AND account_id = target_id` | Deleted last -- `learner_profiles.retention_record_id` pointed at it (spec 009 `data-classification.md`: "deleted alongside the account it describes"). |
| 13 | *(conditional)* `real_guardian_accounts` | the deleted learner's `guardian_id`, only if that guardian has zero remaining linked learners | Implements `data-classification.md`'s existing guardian-auto-deletion rule; when it fires, also runs the `guardian` cascade below for that guardian's own identity fields (a guardian has no other data). |

### Target type: `guardian`

Per research.md R4, this deletes the guardian's own identity **and**
every learner linked to them -- run the `learner` cascade above once
per linked `learner_id`, then:

| # | Table | Match |
|---|---|---|
| 1 | *(all learner-cascade steps, once per linked learner)* | `learner_profiles.guardian_id = target_id` |
| 2 | `real_guardian_accounts` | `guardian_id = target_id` |

### Target type: `instructor`

| # | Table | Match | Note |
|---|---|---|---|
| 1 | `classroom_rosters` disposition, **and** `quiz_assignments.instructor_id` for every assignment on a transferred roster | `instructor_id = target_id` | Resolved at **submission** time (research.md R5), before the `DeletionRequest` is even created: if `transfer_rosters_to` is given, reassigns *both* `classroom_rosters.instructor_id` and `quiz_assignments.instructor_id` (for assignments on that roster) to the successor in the same step -- an assignment surviving under a transferred roster must never keep pointing at the instructor about to be deleted. Rosters with no successor are left in place for step 2 below to delete. |
| 2 | `quiz_assignment_targets` | via `quiz_assignments.assignment_id` where `quiz_assignments.roster_id` is one of the instructor's remaining (untransferred) rosters | Only for rosters not transferred away in step 1. |
| 3 | `quiz_assignments` | `roster_id` in the instructor's remaining (untransferred) rosters | Scoped by `roster_id` only, not `instructor_id` -- after a correct step-1 transfer, no live assignment still carries the deleted instructor's id, so this only ever reaches assignments on rosters about to be deleted anyway. |
| 4 | `classroom_rosters` | `instructor_id = target_id` (rosters not transferred in step 1) | Learner `enrollments`/`enrollment_requests` pointing at a deleted roster are removed as part of this step (roster-scoped, not learner-scoped -- the learner's own account is never touched, FR-008). |
| 5 | `real_instructor_accounts` | `instructor_id = target_id` | |
| 6 | `retention_records` | `account_type = 'instructor' AND account_id = target_id` | Deleted last, same reasoning as the learner cascade's step 12. |

## Explicitly out of cascade scope

- `grading_response_cache` -- deliberately stores no `learner_id`
  (existing docstring, spec 007 FR-009); nothing to delete.
- `content_passage_embedding`, `question_generation_cache`,
  `prerequisite_edge`, `grade_band`, `subject`, `topic` -- content-level
  data, not linked to any real identity.
- Recommendation-report output -- computed on-the-fly from
  `mastery_states`/`assessment_events` (no persisted table); already
  covered once those are deleted in steps 4/6 above.

## Migration

One additive-only column, no backfill needed (defaults to `NULL` for
every existing row, meaning "not currently warned" -- correct for every
row that predates this feature):

```
ALTER TABLE retention_records
  ADD COLUMN inactivity_warning_sent_at TIMESTAMPTZ NULL;
```
