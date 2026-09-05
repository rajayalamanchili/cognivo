# Data Model: Tutor Agent Answer-Shielding

**Feature**: `016-tutor-answer-shielding` | **Date**: 2026-09-04

No new tables. This feature adds two columns to the existing
`tutor_exchanges` table (Milestone 9) and introduces no new persistent
entity -- both of this spec's Key Entities (`Currently-Open Question`,
`Shielding Decision`) are derived reads or extensions of data the
system already records, per `research.md` decisions 1 and 4.

## Modified: `TutorExchange` (`backend/src/models/tutor_exchange.py`)

Two new nullable columns, added by migration, alongside the existing
`grounded`/`retrieved_passage_ids` pair they mirror:

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `shielded` | `Boolean` | No | `false` | `true` when this exchange's answer was a hint-only response rather than a direct one (FR-003). |
| `shielded_question_id` | `UUID` (FK -> `generated_questions.question_id`) | Yes | `NULL` | The specific currently-open question that triggered shielding (FR-007). `NULL` whenever `shielded = false`; also `NULL` in the FR-010 inconclusive-determination case where shielding was applied defensively but no single open question could be confidently identified as the trigger (still `shielded = true` -- see Edge Cases below). |

No change to `shown_at`, `answer_key`, or any other existing column on
`GeneratedQuestion` or `AssessmentEvent` -- FR-009 requires grading and
mastery mechanics stay exactly as they are.

**Invariant**: `shielded_question_id IS NOT NULL` implies
`shielded = true`. The reverse does not hold (an inconclusive
determination can set `shielded = true` with `shielded_question_id =
NULL`).

## Derived (not stored): Currently-Open Question

For a learner and subject, the set of currently-open questions is:

```text
GeneratedQuestion rows where
  learner_id = :learner_id
  AND subject_id = :subject_id
  AND shown_at IS NOT NULL
  AND NOT EXISTS (
    AssessmentEvent row with
      question_id = GeneratedQuestion.question_id
      AND event_type = 'answer_submitted'
  )
  AND NOT EXISTS (
    -- FR-006 / research.md decision 1 correction (`/speckit-analyze`
    -- finding C1): a cancelled instructor-assigned attempt never
    -- transitions its QuizSession.status, so it must be excluded
    -- explicitly rather than relying on status alone.
    QuizAssignmentTarget joined to QuizAssignment where
      QuizAssignmentTarget.quiz_session_id = GeneratedQuestion.quiz_session_id
      AND QuizAssignment.cancelled_at IS NOT NULL
  )
```

This is exactly `questions.py`'s existing `_already_answered()` check,
generalized across all three question-display call sites (practice,
quiz, placement) that already set `shown_at` on the same table
(`research.md` decision 1) -- no new query pattern, applied more
broadly than its current single call site -- plus the second `NOT
EXISTS` clause covering FR-006's "session/attempt ended" branch for a
cancelled instructor-assigned attempt specifically (the only case this
system can actually detect; see research.md decision 1's correction
and spec.md's Edge Cases for why a plain abandoned learner-initiated
quiz has no equivalent signal).

**Multiple open questions**: A learner can have more than one row
match (e.g. an in-progress quiz question and a separate, stale,
never-revisited practice question -- spec.md's Edge Cases). The
shielding classification (`research.md` decision 2) runs the tutor
question against each open question; if more than one matches, the
most recently `shown_at` one is recorded as `shielded_question_id`
(the one the learner is most plausibly asking about right now). An
unrelated open question elsewhere never causes shielding on its own
(User Story 2) -- at least one open question must actually match for
`shielded` to be `true` on confident-determination grounds, though
FR-010's fail-safe can still set it `true` with no match at all.

## Derived (not stored): Shielding Decision

Not a separate row -- it *is* the pair of new `TutorExchange` columns
above, plus the existing `TUTOR_EXCHANGE_COMPLETED` audit-log event
(`assessment_events`, unchanged table, extended payload):

```json
{
  "exchange_id": "...",
  "session_id": "...",
  "retrieved_passage_ids": ["..."],
  "grounded": true,
  "delegation_context_summary": [],
  "shielded": true,
  "shielded_question_id": "..."
}
```

This is the concrete mechanism behind FR-007/SC-003: an inspector
reading either the `TutorExchange` row directly (User Story 3's
existing inspection path, `test_tutor_exchange_inspection.py`) or this
audit-log payload can determine, after the fact, whether and why a
given exchange was shielded -- without asking the Tutor Agent itself.

## Migration

One new Alembic revision, additive-only (two nullable/defaulted
columns, one FK constraint) -- no backfill needed, since every existing
`TutorExchange` row predates this feature and is correctly represented
by `shielded = false, shielded_question_id = NULL` (an already-answered
question by the time shielding could apply, or genuinely never
shielded).
