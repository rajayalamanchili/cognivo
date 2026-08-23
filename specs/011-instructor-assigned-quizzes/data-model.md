# Data Model: Instructor-Assigned Quizzes

**Feature**: `011-instructor-assigned-quizzes` | **Date**: 2026-08-23

No existing table is modified. Two new tables, both additive joins onto
Milestone 7's `classroom_rosters`/`learner_profiles` and Milestone 5's
`quiz_sessions` -- see research.md §1 for why `quiz_sessions` itself
stays untouched.

## Entities

### QuizAssignment (new table: `quiz_assignments`)

| Field | Type | Notes |
|---|---|---|
| `assignment_id` | UUID, PK | |
| `roster_id` | FK -> `classroom_rosters.roster_id`, not null | The roster this assignment was created against (FR-001). |
| `instructor_id` | FK -> `real_instructor_accounts.instructor_id`, not null | The creating instructor -- also derivable via `roster_id`, kept directly on the row so audit/ownership checks don't require a join, matching `RetentionRecord.authorized_by_id`'s existing denormalized-but-justified pattern for "who authorized this." |
| `subject_id` | FK -> `subjects.subject_id`, not null | Resolved and validated (all `topic_ids` belong to it, and it matches `roster.subject_id`) at creation time -- same validation shape `QuizSession.subject_id` already uses (`_resolve_quiz_subject_id`, `quiz.py`). |
| `topic_ids` | JSON list[str], not null | Mirrors `QuizSession.topic_ids`. |
| `question_count` | integer, not null | Mirrors `QuizSession.question_count`. |
| `due_at` | timestamp, nullable | Optional per FR-001/roadmap.md. `NULL` means no due date -- never blocks starting (FR-014 only applies when set). |
| `cancelled_at` | timestamp, nullable | Set by instructor cancellation (research.md §6). `NULL` = active. |
| `created_at` | timestamp, not null | |

### QuizAssignmentTarget (new table: `quiz_assignment_targets`)

| Field | Type | Notes |
|---|---|---|
| `assignment_target_id` | UUID, PK | |
| `assignment_id` | FK -> `quiz_assignments.assignment_id`, not null | |
| `learner_id` | FK -> `learner_profiles.learner_id`, not null | One row per learner targeted at creation time (FR-002/FR-005) -- a snapshot, never added to later (research.md §4). |
| `quiz_session_id` | FK -> `quiz_sessions.quiz_session_id`, nullable | `NULL` until the learner's guardian starts the attempt (FR-006); set exactly once (research.md §3 -- enforces FR-014's single-attempt rule together with the unique constraint below). |
| `created_at` | timestamp, not null | When this learner was targeted. |

**Constraints**:
- `UNIQUE (assignment_id, learner_id)` -- a learner is targeted by a given assignment at most once; combined with "start only writes `quiz_session_id` when it is currently `NULL`," this is the DB-enforced backing for FR-014's single-attempt rule (research.md §3).

**Derived status** (not stored, computed at read time -- same
philosophy as `QuizSession`'s own "derive from `GeneratedQuestion`/
`AssessmentEvent` rows, never duplicate" pattern, spec 005
data-model.md):

| Condition | Reported status (FR-010) |
|---|---|
| `quiz_session_id IS NULL` | `not_started` |
| joined `QuizSession.status = in_progress` | `in_progress` |
| joined `QuizSession.status = completed` | `completed`, with `compute_quiz_summary`'s score |
| joined `QuizSession.status = ended_early` | `ended_early` |

## Relationships

```
ClassroomRoster (M7) ──< QuizAssignment ──< QuizAssignmentTarget >── LearnerProfile (M7)
                                                     │
                                                     └── (nullable) QuizSession (M5, unmodified) ──< GeneratedQuestion (M1/M5/M6, unmodified)
```

## State transitions

`QuizAssignment`: created (active) → optionally cancelled
(`cancelled_at` set). No other transitions -- not editable in place
(spec.md Assumptions).

`QuizAssignmentTarget`: created with `quiz_session_id = NULL` at
assignment creation → `quiz_session_id` set exactly once when the
learner's guardian starts the attempt. The attempt's own
in-progress/completed/ended-early lifecycle is entirely
`QuizSession`'s existing state machine (spec 005), not re-modeled here.
