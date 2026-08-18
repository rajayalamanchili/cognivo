# Tasks: Adaptive Difficulty Quiz

**Input**: Design documents from `/specs/005-adaptive-quiz/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present)

**Tests**: Included. `roadmap.md`'s Milestone 5 Definition of Done makes SC-001 (determinism) and SC-002 (100% of quiz-answered questions verified in mastery state) hard gates and requires Milestones 1-4's full suites to still pass -- so the test tasks below are load-bearing, not optional scaffolding.

**Organization**: Tasks are grouped by user story (spec.md priorities) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete same-phase task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are per `plan.md`'s Project Structure

## Path Conventions

Extends the existing `backend/` + `frontend/` monorepo: `backend/src/{models,services/quiz,api/routes}/`, `backend/alembic/versions/`, `backend/tests/{unit,integration}/`; `frontend/src/{app/quiz,components,services}/`, `frontend/tests/{unit,e2e}/`.

---

## Phase 1: Setup

**Purpose**: Confirm this feature needs no new dependency before any code is written

- [X] T001 [P] Confirm no new dependency is required in `backend/pyproject.toml` or `frontend/package.json` (research.md -- reuses the already-locked FastAPI/SQLAlchemy/Alembic/ADK and Next.js/React/Tailwind stacks; no `uv add` / `npm install` needed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema changes and the two pure algorithms every user story's endpoints call

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Implement `QuizSession` model (`quiz_session_id`, `learner_id`, `subject_id`, `topic_ids`, `question_count`, `status`, `started_at`, `completed_at`) in `backend/src/models/quiz_session.py` per data-model.md
- [X] T003 [P] Add nullable `quiz_session_id` FK column to `GeneratedQuestion` in `backend/src/models/generated_question.py` per data-model.md
- [X] T004 [P] Add `QUIZ_DIFFICULTY_ADJUSTED = "quiz_difficulty_adjusted"` to `AssessmentEventType` in `backend/src/models/enums.py` per data-model.md
- [X] T005 Register `QuizSession` in `backend/src/models/__init__.py`'s imports/`__all__` (depends on T002)
- [X] T006 Alembic migration: create `quiz_sessions` table, add `generated_questions.quiz_session_id` FK column, `ALTER TYPE assessment_event_type ADD VALUE 'quiz_difficulty_adjusted'` (same technique as `533736af33d7_recommendation_event_types.py`, research.md §6) in `backend/alembic/versions/` (depends on T002, T003, T004)
- [X] T007 [P] Unit test: `next_difficulty` step function -- 2 consecutive correct moves up one band, 2 consecutive incorrect moves down one band, streak resets to zero on every band change (including a held bound), holds at `easy`/`hard` without erroring (FR-002, FR-007, research.md §1) in `backend/tests/unit/test_quiz_difficulty.py`
- [X] T008 [P] Unit test: `next_quiz_topic` round-robin selection -- cycles through `topic_ids` in selection order based on questions-generated-so-far count (research.md §2) in `backend/tests/unit/test_quiz_round_robin.py`
- [X] T009 Implement `services/quiz/difficulty.py`: `next_difficulty()` and `current_difficulty_for_topic()` (replay-based, no DB; shared by all three user stories) in `backend/src/services/quiz/difficulty.py` (depends on T007)
- [X] T010 Implement `next_quiz_topic()` pure function (shared by all three user stories) in `backend/src/services/quiz/session.py` (depends on T008)

**Checkpoint**: Foundation ready -- schema migrated, both pure algorithms implemented and regression-tested; user story implementation can now begin.

---

## Phase 3: User Story 1 - Take a quiz that gets harder or easier as you go (Priority: P1) 🎯 MVP

**Goal**: A learner can start a quiz on chosen topic(s) with a fixed question count, have each topic's difficulty adapt via the streak rule, and reach a defined completion state with a score and summary.

**Independent Test**: Given a scripted sequence of correct and incorrect answers within a quiz, confirm the difficulty of each subsequent question moves in the expected direction and the quiz reaches a defined completion state with a score.

### Tests for User Story 1

- [X] T011 [P] [US1] Integration test `POST /api/quizzes` -- first question always at `easy` difficulty for `topic_ids[0]`, `422` on empty/duplicate `topic_ids` or `question_count` outside 1-50 (FR-001), `404` on unknown/unvalidated/cross-subject `topic_ids` (contracts/api.md) in `backend/tests/integration/test_quiz_start.py`
- [X] T012 [P] [US1] Integration test `GET /api/quizzes/{id}/next-question` -- difficulty escalates/de-escalates per the streak rule end to end against a real DB, `409` once the quiz is `completed`/`ended_early` (contracts/api.md) in `backend/tests/integration/test_quiz_next_question.py`
- [X] T013 [P] [US1] Integration test: the dedup-exhaustion → `ended_early` transition itself (FR-008) -- constrain/mock the near-duplicate check so retries exhaust for a topic (mirroring how Milestone 1's tests mock `_run_agent_once`), then confirm no new `GeneratedQuestion` row is created, `QuizSession.status` becomes `ended_early` with `completed_at` set, and `GET /api/quizzes/{id}` still returns a score/summary in the same shape FR-005 describes for a normal completion (analysis finding C1, 2026-08-18) in `backend/tests/integration/test_quiz_ended_early.py`
- [X] T014 [P] [US1] Integration test `POST /api/questions/{id}/answer` extended for quiz questions -- `quiz_difficulty_adjusted` event logged per question (FR-009), `QuizSession.status` flips to `completed` when answered-count reaches `question_count` (research.md §4) in `backend/tests/integration/test_quiz_completion.py`
- [X] T015 [P] [US1] Integration test `GET /api/quizzes/{id}` -- score/summary shape grouped by (topic, difficulty), correct even while `in_progress` (partial tally, contracts/api.md) in `backend/tests/integration/test_quiz_summary.py`
- [X] T016 [P] [US1] Frontend unit test: `QuizSummary` renders score and the per-topic/difficulty breakdown in `frontend/tests/unit/quiz-summary.test.tsx`
- [X] T017 [P] [US1] Frontend unit test: the quiz flow renders distinct states for answering, `completed`, and `ended_early` in `frontend/tests/unit/quiz-flow.test.tsx`

### Implementation for User Story 1

- [X] T018 [US1] Implement `services/quiz/session.py`'s `start_quiz()` and `generate_quiz_question()` -- round-robin via `next_quiz_topic()`, difficulty via `current_difficulty_for_topic()`, dedup via the existing `recent_stems_for_topic()` widened to `question_count` (research.md §3), raising on retry exhaustion (depends on T009, T010, T012, T013)
- [X] T019 [US1] Implement `backend/src/api/routes/quiz.py`'s `POST /api/quizzes` and `GET /api/quizzes/{id}/next-question`, catching retry-exhaustion to set `ended_early` (depends on T018, T011, T012, T013)
- [X] T020 [US1] Extend `backend/src/api/routes/questions.py`'s `answer_question` with the quiz-aware branch: log `quiz_difficulty_adjusted`, flip `QuizSession.status` to `completed` (research.md §4) (depends on T014)
- [X] T021 [US1] Implement `compute_quiz_summary()` in `services/quiz/session.py` and `GET /api/quizzes/{id}` in `quiz.py` (depends on T015, T019)
- [X] T022 [US1] Mount the quiz router (`app.include_router(quiz.router)`) in `backend/src/api/main.py` (depends on T019, T021)
- [X] T023 [P] [US1] Add `startQuiz()`, `getQuizNextQuestion()`, `getQuizSummary()` client functions and types to `frontend/src/services/api.ts` per contracts/api.md (`answerQuestion()` is reused unchanged)
- [X] T024 [US1] Implement `QuizSummary.tsx` component (depends on T023, T016)
- [X] T025 [US1] Scaffold `frontend/src/app/quiz/page.tsx` + `quiz-flow.tsx`: start form (topic(s) + question count) → answering phase (reuses `QuestionCard`/`answerQuestion` unchanged) → completed/ended-early phase (renders `QuizSummary`) (depends on T023, T024, T017)

### Additional Verification for User Story 1

- [X] T026 [US1] Determinism check (SC-001): replay an identical scripted answer sequence against a fresh quiz ten times, confirm identical difficulty progression and final score every run, in `backend/tests/integration/test_quiz_determinism.py` (depends on T018-T022)
- [X] T027 [US1] Zero near-duplicates check (SC-004): run a single-topic quiz with `question_count` greater than Milestone 1's 5-question default lookback, confirm no two questions in the session are near-duplicates, in `backend/tests/integration/test_quiz_no_duplicates.py` (depends on T018-T022)
- [X] T028 [US1] Multi-topic round-robin ordering check (Edge Cases): a 2-topic, 4-question quiz's questions alternate topics in selection order, in `backend/tests/integration/test_quiz_multi_topic_ordering.py` (depends on T018-T022)
- [X] T029 [US1] Playwright E2E test: start a quiz via the UI, answer several questions, reach completion, confirm the score/summary render, in `frontend/tests/e2e/quiz-session.spec.ts` (depends on T025)

**Checkpoint**: User Story 1 is independently functional and demoable -- a full adaptive quiz session works end to end, with determinism, zero-near-duplicate, and `ended_early` guarantees all mechanically verified.

---

## Phase 4: User Story 2 - Quiz results count toward your real progress (Priority: P1)

**Goal**: Prove every question answered within a quiz updates persistent mastery state via the exact same mechanism as a non-quiz question -- no new production code (User Story 1's reused, unmodified `answer_question` already guarantees this by construction, research.md §4).

**Independent Test**: Complete a quiz and confirm every question answered within it appears in the learner's regular assessment-event history and has updated their persistent mastery state, verifiable via the same mastery-state read used elsewhere in the platform.

### Tests for User Story 2

- [ ] T030 [US2] Integration test (SC-002): complete a multi-question quiz, confirm every quiz-answered question appears in `AssessmentEvent` history (`ANSWER_SUBMITTED`, `MASTERY_UPDATED`) and `MasteryState` reflects it via the same read path `GET /mastery-state` already uses, in `backend/tests/integration/test_quiz_mastery_effect.py` (depends on Phase 3 complete)
- [ ] T031 [US2] Integration test (SC-005, FR-006): start a quiz, answer some but not all of its questions, then stop -- confirm `MasteryState` already reflects the answered questions and `QuizSession.status` is still `in_progress` (no distinct "abandoned" status, spec.md Key Entities), in `backend/tests/integration/test_quiz_abandoned.py` (depends on Phase 3 complete)

**Checkpoint**: User Stories 1 and 2 together deliver a fully honest quiz -- adaptive difficulty plus mechanically-verified mastery-state parity.

---

## Phase 5: User Story 3 - Difficulty adjustment stays within real bounds (Priority: P2)

**Goal**: Prove the streak rule's bound-holding behavior (already built into `next_difficulty` in Foundational) holds correctly under the two boundary-stressing scripted runs the story names -- no new production code.

**Independent Test**: Script an "all correct" run and an "all incorrect" run against a content artifact with known difficulty bounds, and confirm both runs reach and hold at the maximum/minimum difficulty without error.

### Tests for User Story 3

- [ ] T032 [US3] Integration test (SC-003): a scripted all-correct run reaches and holds at `hard`; a scripted all-incorrect run reaches and holds at `easy`; neither errors nor requests an undefined level. Also asserts the logged `quiz_difficulty_adjusted` event's `held_at_bound` field is `true` for the decision(s) at the bound (FR-009, analysis finding C2, 2026-08-18), in `backend/tests/integration/test_quiz_difficulty_bounds.py` (depends on Phase 3 complete)

**Checkpoint**: All three user stories independently functional; the bound-holding guarantee -- both observable behavior and its audit-log record -- is mechanically verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression safety and the extensibility gate this milestone shares with every prior one

- [ ] T033 [P] Regression check: run Milestones 1-4's full test suites (`backend/tests/`, excluding this feature's new tests; relevant `frontend/tests/`) and confirm they still pass unmodified (roadmap.md Milestone 5 Definition of Done: "Milestones 1-4's full suites still pass")
- [ ] T034 [P] Run `backend/scripts/check_no_subject_conditionals.py` (unchanged from Milestone 1) -- confirm zero subject-id-keyed conditionals introduced by this feature's new/changed files
- [ ] T035 Run `quickstart.md`'s 10 validation scenarios end to end against a live environment and record results (depends on all prior tasks)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies -- start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion -- BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion only.
- **User Story 2 (Phase 4)**: Depends on User Story 1 being complete -- it verifies behavior US1's endpoints already produce; no new production code of its own.
- **User Story 3 (Phase 5)**: Depends on User Story 1 being complete, for the same reason as US2 -- verifies behavior Foundational's `next_difficulty` already produces.
- **Polish (Phase 6)**: T033/T034 have no hard dependency beyond Foundational; T035 needs everything.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2/US3 -- this is the actual feature build.
- **US2 (P1)**: Verification-only; depends on US1's endpoints existing to exercise.
- **US3 (P2)**: Verification-only; depends on US1's endpoints existing to exercise.

### Within Each User Story

- Tests written and failing before implementation, except US1's "Additional Verification" tasks (T026-T029) and US2/US3's entire phases, which validate already-composed behavior after implementation completes -- mirroring spec 002's and spec 004's own precedent of a late-phase check run after the endpoint exists, rather than a pre-implementation TDD test.
- Models/enum before migration; migration before any DB-touching test or implementation.
- Pure algorithms (`difficulty.py`, round-robin) before the DB-orchestrating service (`session.py`) that calls them.
- Service layer before the API route that calls it; API routes before the router mount.
- Types/client functions (`api.ts`) before the component that consumes them; component before the flow that renders it.

---

## Parallel Example: Foundational

```bash
# Models/enum (independent files, no dependency on an incomplete same-phase task):
Task: "Implement QuizSession model in backend/src/models/quiz_session.py"
Task: "Add quiz_session_id FK column to GeneratedQuestion in backend/src/models/generated_question.py"
Task: "Add QUIZ_DIFFICULTY_ADJUSTED to AssessmentEventType in backend/src/models/enums.py"

# Pure-function unit tests (independent files):
Task: "Unit test next_difficulty in backend/tests/unit/test_quiz_difficulty.py"
Task: "Unit test next_quiz_topic round-robin in backend/tests/unit/test_quiz_round_robin.py"
```

---

## Implementation Strategy

### MVP scope: User Story 1 alone

Unlike User Stories 2 and 3 (which are pure verification of behavior US1's own reused mechanisms already produce, per research.md §4 and Foundational's `next_difficulty` design), User Story 1 is the entire feature build. The smallest real MVP is US1 alone: a learner can take a full adaptive quiz to completion.

1. Complete Phase 1 (Setup) + Phase 2 (Foundational) -- schema migrated, both pure
   algorithms implemented and unit-tested.
2. Complete Phase 3 (US1) -- full quiz session works end to end, with
   determinism (SC-001), zero-near-duplicate (SC-004), and `ended_early`
   (FR-008) guarantees mechanically verified.
3. **STOP and VALIDATE**: run US1's Independent Test. This is the
   smallest demoable increment.
4. Complete Phase 4 (US2) -- mastery-state parity (SC-002) and the
   abandoned-quiz guarantee (SC-005) mechanically verified, no new code.
5. Complete Phase 5 (US3) -- bound-holding (SC-003), including its
   audit-log record, mechanically verified, no new code.
6. Complete Phase 6 (Polish) -- Milestones 1-4 regression check,
   extensibility scan, full quickstart.md validation.

### Incremental delivery

Each phase checkpoint (end of Phase 3, 4, 5, 6) is a point where the
quiz feature is in a coherent, independently testable state.

---

## Notes

- `[P]` tasks = different files, no dependency on an incomplete same-phase task.
- `[Story]` label maps a task to its user story for traceability; Setup, Foundational, and Polish tasks carry no `[Story]` label by design (Foundational's two implementation tasks, T009-T010, serve all three user stories rather than any one of them).
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently before continuing.
- `/speckit-analyze` MUST run before `/speckit-implement` per CLAUDE.md/Constitution Development Workflow -- do not skip it once this task list is approved.
- `/speckit-analyze` ran 2026-08-18 and found 2 coverage gaps (both now closed by T013 and T032's extension) plus 1 stale-status inconsistency (fixed in spec.md directly) -- no CRITICAL findings.
