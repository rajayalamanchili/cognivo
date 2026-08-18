# Data Model: Adaptive Difficulty Quiz

Extends `specs/001-domain-agnostic-core/data-model.md`'s schema. One new
table, one new nullable FK column, one new `AssessmentEventType` enum
value -- no other schema change.

## New entity: `QuizSession`

| Field | Type | Notes |
|---|---|---|
| `quiz_session_id` | UUID, PK | |
| `learner_id` | UUID, FK -> `demo_learner_profiles.learner_id` | |
| `subject_id` | string, FK -> `subjects.subject_id` | All of `topic_ids` must belong to this subject (service-layer check at start, not a DB constraint -- `topic_ids` is a JSON array, not FK-able directly). |
| `topic_ids` | JSON (ordered list of strings) | The learner's chosen topic(s), in selection order -- this order is also the round-robin cycle order (research.md §2). |
| `question_count` | integer | Learner-chosen target; must be between 1 and 50 inclusive (spec.md FR-001, service-layer validation). |
| `status` | enum: `in_progress` \| `completed` \| `ended_early` | See spec.md's Key Entities note: an abandoned quiz is simply one left `in_progress` forever -- no distinct status transition exists for abandonment (FR-006). |
| `started_at` | timestamp, server default now() | |
| `completed_at` | timestamp, nullable | Set when `status` becomes `completed` or `ended_early`; null while `in_progress`. |

**State transitions**: `in_progress` → `completed` (answered-count
reaches `question_count`, set inside `POST /questions/{id}/answer`'s
quiz-aware branch) or `in_progress` → `ended_early` (dedup retries
exhausted while generating the next question, research.md §3). Both are
terminal -- no transition back to `in_progress`.

## Changed entity: `GeneratedQuestion`

| Field | Type | Notes |
|---|---|---|
| `quiz_session_id` | UUID, nullable, FK -> `quiz_sessions.quiz_session_id` | NULL for a non-quiz question (placement, regular practice) -- unchanged for every existing row and every non-quiz code path. Set at generation time for a quiz question, never after. |

No other `GeneratedQuestion` field changes. `difficulty` continues to
be set at generation time from the computed in-quiz band (research.md
§1), exactly as it already is for non-quiz questions.

## Changed entity: `AssessmentEventType` (enum)

One new value: `quiz_difficulty_adjusted` (research.md §6). Logged once
per in-quiz question generated, payload:

```json
{
  "quiz_session_id": "uuid",
  "prior_band": "easy",
  "new_band": "medium",
  "streak_direction": "correct",
  "streak_length_at_decision": 2,
  "held_at_bound": false
}
```

`held_at_bound: true` marks the FR-007 case where the streak threshold
was reached but the band was already at `hard`/`easy` and could not
move further.

## Derived (not persisted): per-topic in-quiz difficulty state

Computed by `services/quiz/difficulty.py`'s pure replay function over a
topic's ordered `(correct: bool)` history within one quiz session
(research.md §1) -- not stored on any row. Inputs to the replay come
from a query joining this quiz's `GeneratedQuestion` rows (filtered by
`quiz_session_id` + `topic_id`, ordered by `generated_at`) to their
`ANSWER_SUBMITTED` `AssessmentEvent.payload["correct"]` value.

## Derived (not persisted): quiz completion summary

`GET /api/quizzes/{quiz_session_id}` computes score and a per-
(topic, difficulty) breakdown by querying the same joined
`GeneratedQuestion`/`AssessmentEvent` rows -- no separate summary table.
See contracts/api.md for the exact response shape.

## Entity relationship summary

```text
QuizSession 1---* GeneratedQuestion (via quiz_session_id, nullable)  (NEW)
GeneratedQuestion 1---1 AssessmentEvent (ANSWER_SUBMITTED, MASTERY_UPDATED, quiz_difficulty_adjusted)  (existing pattern, extended)
QuizSession *---1 DemoLearnerProfile                                  (NEW)
QuizSession *---1 Subject                                             (NEW)
```
