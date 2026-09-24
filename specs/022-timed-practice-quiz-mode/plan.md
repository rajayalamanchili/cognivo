# Implementation Plan: Timed Practice and Quiz Mode

**Branch**: `032-timed-practice-quiz-mode` | **Date**: 2026-09-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-timed-practice-quiz-mode/spec.md`

## Summary

Let a learner opt into a fixed time limit for a quiz (extending the
existing `quiz_sessions` mechanism) or ordinary practice (a new,
narrowly-scoped `practice_sessions` concept, created only for timed
practice), with server-side, lazily-evaluated expiry -- never a
background timer process -- auto-submitting the session using whatever
answers exist when time runs out. Scoring stays identical to an
untimed session (the timer is purely a bounding/UX constraint, never a
scoring input); a new manual "end now" action lets a learner stop a
timed session early. Untimed practice and quizzes are unaffected in
session/scoring/question-selection behavior. Post-plan `/speckit-clarify`
(2026-09-23) added FR-011: every answered question, across all five
flows (placement, untimed/timed practice, untimed/timed quiz) now
records how long the learner took to answer, computed server-side --
a payload-only audit-log extension, no schema migration of its own.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript (frontend) --
unchanged from every prior milestone.

**Primary Dependencies**: FastAPI, SQLAlchemy/Alembic, Google ADK
(Sequencing Agent reused unmodified), Next.js -- no new dependency
(research.md §6).

**Storage**: PostgreSQL via Neon -- one new table (`practice_sessions`),
one new nullable column each on `quiz_sessions` and
`generated_questions`, one new `AssessmentEventType` enum member
(data-model.md). FR-011's per-question timing is a JSON payload key on
the existing `answer_submitted` event, not a schema change.

**Testing**: `pytest` (backend), `Vitest` (frontend) -- same frameworks,
new test modules for the lazy-expiry check and the two new session
types' endpoints.

**Target Platform**: Vercel (Python Function backend + Next.js
frontend), same as every prior milestone.

**Project Type**: Web application (existing `backend/` + `frontend/`
split).

**Performance Goals**: No new performance target beyond existing
per-request latency budgets (`tech-stack.md`'s Vercel section) -- the
lazy-expiry check is a single `datetime` comparison against an
already-loaded row, not a new query.

**Constraints**: Must not introduce a persistent background process
(Constitution Principle IX) -- resolved by the lazy, per-request expiry
check (research.md §1), not a cron job or scheduler.

**Scale/Scope**: Two new session-bounded flows (timed quiz, timed
practice) layered on existing single-learner-at-a-time usage patterns;
no new scale dimension.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | Sequencing Agent's topic selection is reused unmodified for timed practice; the timer wraps it, never replaces or bypasses it. | PASS |
| II. Generated Content Graded Against a Rubric | FR-004 keeps scoring identical to an untimed session -- no new grading logic, no timer-based rubric change. | PASS |
| III. One Engine, Many Subjects | No subject-id-keyed conditional anywhere in the timer/session logic -- `time_limit_seconds`, `expires_at`, and `end_reason` are all subject-agnostic. | PASS |
| IV. Agent Boundaries Reflect Real Responsibility | No new agent, no change to any existing agent's boundary -- this is session/data-layer and API work only. | PASS |
| V. Logged and Explainable | New `timed_session_ended` audit event (data-model.md) answers "how did this session end" for every timed session; FR-011's `time_spent_seconds` extends `answer_submitted` for every flow, timed or not; no new agent invocation, so no new Langfuse trace requirement beyond what question-generation calls already produce. | PASS |
| VI. Agent Boundaries Match Deployment Boundaries | N/A -- no new A2A service. | PASS |
| VII. Spec Before Code | This plan follows an approved `spec.md` with all `[NEEDS CLARIFICATION]` markers resolved. | PASS |
| VIII. No Real Learner Data Until Privacy Is Specified | No new PII collected -- `time_limit_seconds`/`elapsed_seconds`/`end_reason` are non-identifying session config/outcome data. No demo-account changes. | PASS |
| IX. Deployable and Demoable, Stateless Vercel Model | Initially at risk: a naive "active countdown" design would need a persistent process. Resolved by research.md §1's lazy, per-request expiry check -- no background process introduced. | PASS (after research.md §1) |
| X. Staged Release Discipline | Standard feature-branch → `staging` → `main` flow, no exception requested. | PASS |

No violations requiring justification -- Complexity Tracking section
below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/022-timed-practice-quiz-mode/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── quiz_session.py          # EXTENDED: + time_limit_seconds
│   │   ├── practice_session.py      # NEW
│   │   ├── generated_question.py    # EXTENDED: + practice_session_id
│   │   └── enums.py                 # EXTENDED: + AssessmentEventType.TIMED_SESSION_ENDED
│   ├── services/
│   │   └── quiz/
│   │       └── session.py           # EXTENDED: lazy-expiry check, end-reason logic, reused by
│   │                                 # both session types; also now owns the shared
│   │                                 # ALLOWED_TIME_LIMIT_SECONDS/validate_time_limit_seconds
│   │                                 # (moved out of quiz.py so quiz + practice can't drift)
│   └── api/
│       └── routes/
│           ├── quiz.py               # EXTENDED: time_limit_seconds, /end route
│           ├── practice_sessions.py  # NEW: start/next-question/end/summary, reuses
│           │                         # questions.py's generate_and_persist_next_question
│           ├── questions.py          # EXTENDED: FR-011 time_spent_seconds in answer_submitted
│           │                         # payload (practice/quiz), timed-session expiry rejection
│           │                         # (US1/US2), and a new exported
│           │                         # generate_and_persist_next_question (extracted from
│           │                         # get_next_question so practice_sessions.py can reuse it
│           │                         # rather than duplicating ~50 lines)
│           ├── placement.py          # EXTENDED: FR-011 time_spent_seconds in answer_submitted
│           │                         # payload (placement's own submit route -- found during
│           │                         # implementation, not in the original file list)
│           └── main.py               # EXTENDED: registers practice_sessions.router
│           (quiz.py + practice_sessions.py also EXTENDED again, US3: summary routes
│           gain time_limit_seconds/elapsed_seconds/end_reason via T008's helper)
├── alembic/versions/
│   └── 5033078cfc81_timed_practice_quiz_mode.py  # practice_sessions table, 2 new
│                                                   # columns, 1 new enum value
└── tests/
    ├── unit/                          # test_timed_session_expiry.py,
    │                                   # test_timed_session_manual_end.py, test_answer_time_spent.py
    ├── contract/                      # test_quiz_timed_*.py, test_quiz_manual_end.py,
    │                                   # test_practice_session_*.py, test_quiz_timed_summary.py
    └── integration/                   # test_timed_quiz_full_attempt.py,
                                        # test_timed_practice_full_session.py,
                                        # test_ordinary_practice_unaffected.py

frontend/
├── src/
│   ├── components/
│   │   ├── SessionCountdown.tsx      # NEW: client-side countdown built from server expires_at
│   │   └── SessionTimingSummary.tsx  # NEW (US3): shared time-limit/time-used/end-reason
│   │                                 # display, reused by QuizSummary.tsx and practice-flow's
│   │                                 # new ended screen -- not in the original file list
│   ├── lib/
│   │   └── time-limit-options.ts     # NEW: shared TIME_LIMIT_OPTIONS (quiz + practice pickers
│   │                                 # can't drift apart) -- not in the original file list
│   ├── services/
│   │   └── api.ts                    # EXTENDED: expires_at, time_limit_seconds, endQuiz(),
│   │                                 # startPracticeSession/getPracticeNextQuestion/
│   │                                 # endPracticeSession/getPracticeSessionSummary
│   └── app/
│       ├── quiz/quiz-flow.tsx         # EXTENDED: time-limit picker, countdown, end-now button
│       └── practice/practice-flow.tsx # EXTENDED: new "start" screen (subject + time-limit
│                                       # picker) before either untimed or timed practice
│                                       # begins; US3 adds a fetched summary on the ended screen
└── tests/unit/                        # session-countdown.test.tsx, practice-flow.test.tsx
                                        # (actual location: tests/unit/, kebab-case, matching
                                        # this repo's real convention, not this row's original guess)
```

**Structure Decision**: Existing `backend/` + `frontend/` split,
unchanged. No new top-level project or service -- this is data-model
and route additions to the existing backend plus UI additions to the
existing frontend, following the same "Option 2: Web application"
shape every prior milestone has used.

## Complexity Tracking

*No Constitution Check violations -- section intentionally empty.*
