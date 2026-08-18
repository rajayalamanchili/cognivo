# Implementation Plan: Adaptive Difficulty Quiz

**Branch**: `005-adaptive-quiz` | **Date**: 2026-08-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-adaptive-quiz/spec.md`

## Summary

A bounded, named quiz session where each topic's difficulty adapts
in-session via a deterministic streak rule (two consecutive same-
direction answers move one difficulty band, resetting the streak), with
questions cycling round-robin across the learner's chosen topic(s).
Every question answered updates the learner's persistent mastery state
through the exact same, unmodified mechanism a non-quiz question already
uses (`POST /api/questions/{id}/answer`, extended internally rather than
duplicated). Per this feature's Clarifications, `QuizSession` is a new,
thin persisted Postgres entity -- required because a quiz's
configuration (topics, target question count) must survive across
multiple stateless Vercel requests before its first question even
exists, unlike placement's single-shot batch flow. No new agent: in-quiz
difficulty selection is new deterministic service code layered on the
existing Assessment-Generation Agent's question generation, exactly as
spec.md's Assumptions require.

## Technical Context

**Language/Version**: Python 3.12 (backend, matches `backend/pyproject.toml`) + TypeScript/Next.js (frontend, matches `frontend/package.json`) -- extends the existing monorepo, no new language/runtime.

**Primary Dependencies**: Backend -- FastAPI, SQLAlchemy 2.0, Pydantic 2, Alembic, Google ADK (all already locked, no new dependency; reuses the existing Assessment-Generation Agent unchanged). Frontend -- Next.js, React, Tailwind (all already locked; reuses `QuestionCard` unchanged for in-quiz question display).

**Storage**: PostgreSQL via Neon -- one new table (`quiz_sessions`), one new nullable FK column (`generated_questions.quiz_session_id`), one new `assessment_event_type` enum value (`quiz_difficulty_adjusted`). One new Alembic migration, following the exact enum-extension technique spec 002's migration already established (research.md §6).

**Testing**: `pytest` (backend, `backend/tests/{unit,integration}/`) for the difficulty-replay pure function, round-robin selection, quiz session lifecycle, and the three new/extended endpoints; `Vitest` + React Testing Library (frontend component tests) for the quiz flow's phases and summary rendering; `Playwright` (E2E) for a full quiz session against a live backend, per `tech-stack.md`.

**Target Platform**: Same deployed Vercel Services project (FastAPI ASGI backend + Next.js frontend) as Milestones 1-4 -- three new backend routes mounted on the existing `app`, one new Next.js route (`/quiz`). No new deployment unit.

**Project Type**: Web service (existing `backend/` + `frontend/` monorepo), continuing the pattern Milestone 4 established of touching both backend and frontend in one milestone.

**Performance Goals**: No SC in spec.md states a latency target. Each in-quiz question generation is one Assessment-Generation Agent LLM call, same cost/latency profile as Milestone 1's `next-question` -- no new performance concern introduced.

**Constraints**: Stateless per request (Constitution Principle IX) -- `QuizSession` persists all cross-request state; no per-topic difficulty/streak counter is persisted (research.md §1), it is re-derived by replaying that topic's answer history on every read, keeping there being exactly one source of truth (the answer history itself).

**Scale/Scope**: Single learner per quiz session (spec.md Assumptions, same solo-learner scope as every prior milestone); a quiz spans 1+ topics within one subject, round-robin ordered; `question_count` is learner-chosen, bounded to 1-50 inclusive (spec.md FR-001, added during checklist review 2026-08-18).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | In-quiz difficulty selection is a new, explicit, deterministic streak rule (research.md §1) -- not an LLM guess, and distinct from (not a replacement for) the Sequencing Agent's own BKT-based mastery model, which this feature does not touch. | PASS |
| II. Generated content graded against a rubric | Quiz questions are generated via the unchanged Assessment-Generation Agent flow -- same answer-key-generated-alongside-the-question guarantee as every other question on the platform. No new generation path. | PASS |
| III. One engine, many subjects | Every new read/write is parameterized by `topic_id`/`subject_id` values read from the request or DB, no subject-id-keyed conditional -- covered by the existing `check_no_subject_conditionals.py` scan. | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent (spec.md Assumptions, reiterated in CLAUDE.md's Milestone 5 note). In-quiz difficulty adjustment is new deterministic service code (`services/quiz/`), the same kind of non-agent addition Milestone 4's `preview_topic_priority` was to the Sequencing Agent. | PASS |
| V. Logged and explainable | Every in-quiz difficulty decision is logged as a new `quiz_difficulty_adjusted` `AssessmentEvent` (FR-009, data-model.md) and wrapped in `traced_request()` since it's part of an Assessment-Generation Agent call -- both the pedagogical audit log and the Langfuse trace are covered, matching Principle V's "both required, not interchangeable." | PASS |
| VI. A2A justified by concrete need | No new agent boundary introduced (see Principle IV row); N/A. | N/A |
| VII. Spec before code | This plan follows the approved, clarified spec.md (Clarifications session 2026-08-18). | PASS |
| VIII. No real learner data | Reads/writes only `DemoLearnerProfile`-scoped rows, same as every prior milestone. No new learner-data surface. | PASS |
| IX. Deployable and demoable | Three new routes mount on the already-deployed FastAPI app; one new Next.js route on the already-deployed frontend. `QuizSession`'s persisted-not-in-memory design is itself the direct consequence of this principle (Clarifications, Technical Context above). | PASS |
| X. Staged release discipline | Feature branch `005-adaptive-quiz` -> PR into `staging`, per existing workflow. | PASS (process, not a design gate) |

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/005-adaptive-quiz/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output
└── tasks.md               # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── quiz_session.py          # NEW: QuizSession model
│   │   └── generated_question.py    # + nullable quiz_session_id FK column
│   ├── services/
│   │   └── quiz/
│   │       ├── __init__.py           # NEW
│   │       ├── difficulty.py         # NEW: pure next_difficulty/current_difficulty_for_topic
│   │       │                          # (replay-based, research.md §1) -- no DB
│   │       └── session.py            # NEW: DB-orchestration -- start_quiz,
│   │                                    # generate_quiz_question (round-robin + dedup +
│   │                                    # ended_early, research.md §2/§3), compute_summary
│   └── api/routes/
│       └── quiz.py                   # NEW: POST /api/quizzes, GET .../next-question,
│                                        # GET /api/quizzes/{id}; also extends
│                                        # questions.py's answer_question with the
│                                        # quiz-aware branch (research.md §4)
└── alembic/versions/
    └── <new>_quiz_sessions.py        # NEW: quiz_sessions table, quiz_session_id FK,
                                         # quiz_difficulty_adjusted enum value

frontend/
├── src/
│   ├── app/
│   │   └── quiz/
│   │       ├── page.tsx              # NEW
│   │       └── quiz-flow.tsx         # NEW: start form -> answering (reuses
│   │                                    # QuestionCard) -> completed/ended_early summary
│   ├── components/
│   │   └── QuizSummary.tsx           # NEW: FR-005's score + per-topic/difficulty summary
│   │                                    # (QuestionCard.tsx is REUSED unchanged for
│   │                                    # in-quiz question display)
│   └── services/
│       └── api.ts                    # + startQuiz(), getQuizNextQuestion(),
│                                        # getQuizSummary() (answerQuestion() REUSED
│                                        # unchanged, research.md §4)
└── tests/
    └── (unit/e2e test files added at /speckit-tasks time)
```

**Structure Decision**: Extends the existing `backend/` + `frontend/`
monorepo -- no new project. Backend follows the established
`services/<name>/` (pure-rule-plus-DB-orchestration split, per
`weak_area.py`/`next_step.py`/`agents/sequencing/agent.py`'s existing
precedent) + `api/routes/<name>.py` (thin HTTP layer) split; the one
new route file also extends `questions.py`'s existing `answer_question`
in place rather than duplicating it (research.md §4). Frontend follows
the established `app/<route>/page.tsx` + `<route>-flow.tsx` (data
fetching/state machine) + `components/` (presentational) split already
used by `app/practice/{page,practice-flow}.tsx` + `components/QuestionCard.tsx`.

## Post-Design Constitution Check

*Re-checked after Phase 1 (data-model.md, contracts/api.md,
quickstart.md).* Phase 1 introduced two concrete decisions beyond the
Phase 0 Constitution Check above: (1) reusing `POST /api/questions/{id}/answer`
unmodified in its response contract rather than adding a
quiz-specific answer endpoint (research.md §4), and (2) deriving both
in-quiz difficulty state and the completion summary from existing rows
at read time rather than persisting either (research.md §1, data-model.md).
Neither revisits a `tech-stack.md`-locked choice (framework, database,
deployment target, agent boundaries) -- both are applications of
patterns Milestone 1/4 already established. All ten principles
re-checked above still PASS; no new gate failure.

## Complexity Tracking

*No Constitution Check violations -- table intentionally omitted.*
