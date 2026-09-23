# Phase 1 Data Model: Timed Practice and Quiz Mode

**Feature**: `022-timed-practice-quiz-mode` | **Date**: 2026-09-23

See `research.md` §1-§3 for the design decisions this model follows.

## `quiz_sessions` (EXTENDED)

One new nullable column on the existing table
(`backend/src/models/quiz_session.py`):

| Column | Type | Notes |
|---|---|---|
| `time_limit_seconds` | `Integer`, nullable | `NULL` = untimed (today's unchanged default, FR-009). When set, `expires_at` is derived as `started_at + time_limit_seconds`, never stored. |

No other column changes. `status`/`started_at`/`completed_at` are
reused exactly as today; `ended_early` already covers "session
terminated before reaching its configured question count" for any
reason (research.md §3's `end_reason` in the audit event distinguishes
*why*, so the status column itself doesn't need a new member).

## `practice_sessions` (NEW)

A thin header row, deliberately shaped like `quiz_sessions` (spec.md's
Key Entities, research.md §2). Created only when a learner opts into
timed practice -- never for ordinary untimed practice (FR-008).

| Column | Type | Notes |
|---|---|---|
| `practice_session_id` | `UUID`, PK | `default=uuid.uuid4`, matching every other session/entity PK in this codebase. |
| `learner_id` | `UUID`, FK → `learner_profiles.learner_id` | NOT NULL. |
| `subject_id` | `str`, FK → `subjects.subject_id` | NOT NULL. Practice is already single-subject per call (`GET /next-question`'s required `subject_id` query param) -- this session just persists that same scoping across the timed window. |
| `time_limit_seconds` | `Integer` | NOT NULL -- this table only exists for timed sessions, so unlike `quiz_sessions.time_limit_seconds` this one is never null. |
| `status` | `QuizSessionStatus` (reused enum) | `in_progress` / `completed` / `ended_early`, default `in_progress`. Reuses the existing enum rather than defining a duplicate one -- same three states apply identically. |
| `started_at` | `DateTime(timezone=True)` | `server_default=func.now()`. |
| `completed_at` | `DateTime(timezone=True)`, nullable | Set when status leaves `in_progress`. |

`practice_sessions` has no `topic_ids`/`question_count` columns --
unlike a quiz, practice has no pre-committed topic list or fixed
question count; it ends only by timer expiry or manual early-end
(FR-003/FR-010), never by "reached the configured count" (there isn't
one). `completed` therefore never applies to a practice session in
practice (no natural end state besides timer/manual) but is kept for
symmetry with `QuizSessionStatus` and to leave room for a future
question-count option without a schema change.

## `generated_questions` (EXTENDED)

One new nullable column (`backend/src/models/generated_question.py`),
parallel to the existing `quiz_session_id`:

| Column | Type | Notes |
|---|---|---|
| `practice_session_id` | `UUID`, nullable, FK → `practice_sessions.practice_session_id` | `NULL` for ordinary practice and for quiz questions (unchanged today). Set only for a question generated during a timed practice session. Mutually exclusive with `quiz_session_id` in practice -- a question is tagged to at most one session concept, never both. |

## `AssessmentEventType` (EXTENDED enum)

One new member: `timed_session_ended` (research.md §3). Written once
per timed session, on transition out of `in_progress`, for both
`quiz_sessions` and `practice_sessions`.

**Payload shape**:
```json
{
  "session_type": "quiz",
  "session_id": "uuid",
  "time_limit_seconds": 1800,
  "elapsed_seconds": 1742,
  "end_reason": "timer_expired"
}
```
`end_reason` ∈ `{"completed", "timer_expired", "manually_ended_early"}`
(spec.md FR-003/FR-004/FR-010). `elapsed_seconds` is computed once at
transition time (`completed_at - started_at`), not re-derived on every
read.

## State transitions (both `quiz_sessions` and `practice_sessions`)

```
in_progress --[question_count reached, quiz only]--> completed
in_progress --[timer expires, lazily checked, research.md §1]--> ended_early
in_progress --[learner calls the new /end endpoint, timed only]--> ended_early
in_progress --[left untouched]--> in_progress forever (existing "abandoned" precedent, unchanged)
```

Every transition out of `in_progress` for a *timed* session writes one
`timed_session_ended` event. Untimed sessions (`time_limit_seconds IS
NULL`) get no such event -- zero new behavior, per FR-009.
