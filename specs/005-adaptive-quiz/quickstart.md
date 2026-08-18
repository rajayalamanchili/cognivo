# Quickstart: Adaptive Difficulty Quiz

**Feature**: `005-adaptive-quiz` | **Date**: 2026-08-18

Validates a full quiz session end to end, against the already-deployed
Milestone 1-4 backend plus this feature's new `quiz_sessions` table and
three new/extended endpoints. See `data-model.md` for entity detail and
`contracts/api.md` for exact request/response shapes.

## Prerequisites

- Same as `specs/001-domain-agnostic-core/quickstart.md` (Postgres, both
  content artifacts loaded, seeded `DemoLearnerProfile`) -- plus this
  feature's migration (`quiz_sessions` table, `GeneratedQuestion.quiz_session_id`,
  `quiz_difficulty_adjusted` enum value) applied via `alembic upgrade head`.

## Run locally

Same as `specs/001-domain-agnostic-core/quickstart.md`'s Run locally
section, plus load `/quiz` in the frontend (new route).

## Validation scenario: a full quiz session

Maps directly to spec.md's three User Stories' Acceptance Scenarios.

1. **Start a quiz** (FR-001)
   `POST /api/quizzes` with one topic and `question_count: 6` -> confirm
   a `quiz_session_id` and a first question at `easy` difficulty are
   returned.

2. **Difficulty escalates on two consecutive correct answers** (User
   Story 1, FR-002, FR-003)
   Answer the first two questions correctly via
   `POST /api/questions/{id}/answer` (score each with
   `GET /api/quizzes/{id}/next-question` in between) -> confirm the
   third question's `difficulty` is one band above the first two's.
   Answer two more correctly -> confirm difficulty escalates again
   (or holds at `hard` if already there).

3. **Difficulty de-escalates on two consecutive incorrect answers**
   (User Story 1, FR-002)
   Starting fresh, answer two questions incorrectly -> confirm the next
   question's difficulty is one band below the starting band (or holds
   at `easy`).

4. **Determinism check** (SC-001)
   Replay the exact same scripted answer sequence against a fresh quiz
   ten times -> confirm the resulting difficulty progression and final
   score are identical every run.

5. **Quiz completion state** (User Story 1 Acceptance Scenario 3,
   FR-005)
   Answer all `question_count` questions -> confirm the next
   `GET .../next-question` call now returns `409`, and
   `GET /api/quizzes/{id}` reports `status: "completed"` with a score
   and a per-topic/per-difficulty summary.

6. **Mastery state updates exactly like a non-quiz question** (User
   Story 2, SC-002)
   After completing a quiz, call `GET /api/learners/{learner_id}/mastery-state`
   for the quiz's subject -> confirm every quiz-answered topic's
   `update_count` reflects those answers, updated via the same BKT
   mechanism `POST /api/questions/{id}/answer` already uses outside
   quizzes.

7. **Abandoned quiz still keeps its answered questions' mastery effect**
   (User Story 2 Acceptance Scenario 2, SC-005)
   Start a quiz, answer 2 of its 6 questions, then stop (never call
   `next-question` again) -> confirm `GET /api/learners/{learner_id}/mastery-state`
   already reflects those 2 answers, and `GET /api/quizzes/{id}` still
   reports `status: "in_progress"` (no distinct "abandoned" status --
   spec.md's Key Entities note).

8. **Difficulty holds at the bounds** (User Story 3, SC-003)
   Script an "all correct" run long enough to reach `hard` and confirm
   it holds there (never a 4xx/5xx from requesting a level past `hard`).
   Separately, script an "all incorrect" run and confirm it holds at
   `easy` symmetrically.

9. **Zero near-duplicates within one quiz session** (SC-004)
   Run a quiz with `question_count` higher than Milestone 1's default
   5-question dedup lookback (e.g. 8) on a single topic -> confirm no
   two questions in that session have near-duplicate stems, verified by
   the same similarity check `services/dedup/checker.is_near_duplicate`
   already uses.

10. **Multi-topic round-robin ordering** (Edge Cases)
    Start a quiz with `topic_ids: ["topic-a", "topic-b"]` and
    `question_count: 4` -> confirm the four questions' `topic_id`
    values alternate `a, b, a, b` in that order.
