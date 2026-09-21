# Implementation Plan: Age-Adaptive Learner Experience

**Branch**: `019-age-adaptive-learner-experience` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-age-adaptive-learner-experience/spec.md`

## Summary

Three independently-shippable pieces of interaction-model adaptation by
grade band, layered on top of Milestone 15's `grade_bands`/
`GradeProgress` entity: (1) browser-native read-aloud for grades 1-2,
added once to the single `QuestionCard` component every flow already
shares; (2) a four-tier guardian-mediation model (co-present/check-in/
opt-in-nudges/independent) that determines, at quiz-session start,
whether a short-lived hand-off token is minted so the learner's device
can continue a quiz without the guardian's own session present for
every request; and (3) a client-side pacing checkpoint that varies
recommended quiz length/reinforcement cadence by grade band. Plan-time
research surfaced two facts the spec didn't originally account for --
the codebase has no bounded session concept outside Milestone 5's
`QuizSession`, and real learners have no login of their own (every
real-learner quiz session already runs entirely on the guardian's own
session) -- both resolved via `spec.md`'s plan-time Clarifications and
reflected throughout this plan. One new nullable column
(`quiz_assignment_targets.guardian_viewed_at`), one new enum
(`MediationTier`), one new `AssessmentEventType` value, and one new use
of the existing `pyjwt` dependency (a scoped hand-off token, distinct
from a login session). No new table, no new agent, no new A2A service,
no new external dependency.

## Technical Context

**Language/Version**: Python 3.12 (`backend/`, unchanged); TypeScript/
Next.js (`frontend/`, unchanged). No new language or runtime.

**Primary Dependencies**: None new. `pyjwt` (already locked for
guardian/instructor session JWTs, `tech-stack.md`'s Authentication
section) gains a second, distinct token purpose (`research.md`
Decision 4). The browser's native Web Speech API is used for read-aloud
-- a platform capability, not an npm dependency (`research.md`
Decision 1).

**Storage**: PostgreSQL (Neon), via one new nullable column
(`quiz_assignment_targets.guardian_viewed_at`) and one new
`AssessmentEventType` enum value (`guardian_mediation_applied`). No new
table. See `data-model.md`.

**Testing**: `pytest` (backend: new pure-function tests for
`determine_mediation_tier`, `issue_handoff_token`/`verify_handoff_token`,
and the extended `assert_quiz_session_access`; integration tests for
the extended start/next-question/answer/summary/list routes); `Vitest`
(frontend: `QuestionCard`'s read-aloud control, `pacing.ts`'s
checkpoint logic, `LearnerAssignments.tsx`'s handoff-token plumbing and
unviewed-activity badge). Same frameworks already locked -- no new
testing dependency.

**Target Platform**: Vercel serverless functions (`backend`,
`frontend`), unchanged. Hand-off token verification is a stateless JWT
decode plus the same `QuizSession` status lookup the route already
performs -- no new persistent connection, no new background process.

**Project Type**: Web application (existing `backend/` + `frontend/`).
No new service.

**Performance Goals**: None new. Read-aloud is entirely client-side
(zero backend load). Hand-off token verification adds one JWT decode
per request, negligible relative to the existing DB round trip on the
same route.

**Constraints**:
- "Session" means Milestone 5's `QuizSession` specifically; ordinary,
  non-quiz practice is unaffected (`spec.md`'s first plan-time
  Clarification).
- Guardian-initiated start is universal across every tier -- there is
  no real-learner quiz-session-creation path today other than
  `start_assignment_attempt` (`spec.md`'s second plan-time
  Clarification, `research.md` Decision 4).
- A hand-off token is additive to, never a replacement for, the
  guardian's own session -- a guardian's session remains valid for any
  tier's quiz session throughout (`spec.md` Assumptions).
- No change to question content, difficulty selection, or topic
  ordering (FR-010) -- this feature touches only the interaction model.
- No new `tech-stack.md` external dependency; one new row documenting
  the hand-off-token JWT usage is added to its existing Authentication
  section (this is a new *pattern* on an already-locked technology, not
  a new technology choice).

**Scale/Scope**: Touches `backend/` (1 new pure-function module, 1
modified enum, 1 modified model + migration, 2 extended service
functions, 3 extended routes) and `frontend/` (1 extended shared
component, 1 new small pacing lookup, 1 extended guardian-facing
component). No change to `grading-agent/`, `tutor-agent/`, or any other
independently-deployed service, and no change to Milestone 15's own
grade-band/content-difficulty logic.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | `determine_mediation_tier()` is a pure, deterministic function of `GradeProgress.unlocked_grade` -- never an LLM impression. No mastery-model change of any kind. | PASS |
| II. Generated Content Graded Against a Rubric | Unaffected -- this feature touches read-aloud, guardian mediation, and pacing only; no question generation or grading path is touched (FR-010). | PASS |
| III. One Engine, Many Subjects | Tier determination, read-aloud gating, and pacing are all keyed on grade band/`unlocked_grade`, never on `subject_id`. FR-013/SC-008 explicitly require zero behavior change for an ungraded subject like `biology`; `determine_mediation_tier()` returning `None` for "no `GradeProgress` row" (rather than a subject-specific branch) is what guarantees this (`research.md` Decision 3). `check_no_subject_conditionals.py` must stay clean. | PASS (verify at implement time) |
| IV. Agent Boundaries Reflect Real Responsibility | No new agent. Tier determination is a new pure-function service module, not an agent -- it has no LLM call, no independent evaluation criterion, and no failure mode an agent boundary would meaningfully isolate. | PASS |
| V. Every Decision Logged and Explainable | FR-012: `GUARDIAN_MEDIATION_APPLIED` (new `AssessmentEventType`, once per quiz-session start) and `read_aloud_used` (new field on the existing `ANSWER_SUBMITTED` payload) both satisfy SC-007. Separately: this feature adds zero new agent/LLM invocations, so there is no new Langfuse tracing surface to add -- the existing trace coverage of quiz-session start/next-question/answer is unaffected and unchanged. | PASS |
| VI. Agent Boundaries Match Deployment Boundaries | No new A2A service -- everything stays local to `backend`/`frontend`. | PASS |
| VII. Spec Before Code | This plan follows an approved, `/speckit-clarify`'d `spec.md` (three Clarification sessions, the last two at plan time after real architectural gaps surfaced); `/speckit-tasks` and `/speckit-analyze` still required before `/speckit-implement`. | PASS |
| VIII. No Real Learner Data Until Privacy Specified | No new data category -- reads existing `GradeProgress`/`LearnerProfile`/`QuizAssignmentTarget` state, all already gated by Milestone 7's real-data approval. Demo learners are structurally unaffected (their quiz sessions are never assignment-linked, so none of this feature's checks ever engage -- `research.md` Decision 4/Decision 3). | PASS |
| IX. Deployable and Demoable | Hand-off token verification is a stateless JWT decode inside the existing serverless function; the new `guardian_viewed_at` column is a normal DB write, not in-memory state. No new persistent process. | PASS |
| X. Staged Release Discipline | Enforced at PR time (staging -> main), not a plan-time gate. | N/A here |

No violations. Complexity Tracking is not needed.

**Post-Phase-1 re-check**: `research.md` and `data-model.md` confirm the
design stayed inside this table's assumptions -- one new nullable
column, one new enum, one new event type, one extended (not new) use of
`pyjwt`, no new table, no new agent, no new A2A service, no subject-id
branching. `assert_quiz_session_access`'s tier lookup re-derives from
live `GradeProgress` state on every call rather than trusting a cached
value, which keeps Principle I's "reproducible and explainable" bar
intact for a decision made at every request, not just at session start.
The gate still passes.

## Project Structure

### Documentation (this feature)

```text
specs/019-age-adaptive-learner-experience/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── enums.py                       # MODIFIED: + MediationTier, + GUARDIAN_MEDIATION_APPLIED
│   │   └── quiz_assignment_target.py      # MODIFIED: + guardian_viewed_at (nullable)
│   ├── services/
│   │   ├── mediation/
│   │   │   └── tier.py                    # NEW: determine_mediation_tier() (pure function)
│   │   ├── auth/
│   │   │   └── tokens.py                  # MODIFIED: + issue_handoff_token, + verify_handoff_token
│   │   └── quiz_assignment/
│   │       └── assignment.py              # MODIFIED: assert_quiz_session_access (renamed/extended),
│   │                                       #           start_assignment_attempt mints handoff_token,
│   │                                       #           guardian-view sets guardian_viewed_at
│   └── api/
│       └── routes/
│           ├── quiz.py                    # MODIFIED: accepts X-Quiz-Handoff-Token header
│           ├── questions.py               # MODIFIED: same
│           └── quiz_assignments.py        # MODIFIED: handoff_token in start response,
│                                           #           has_unviewed_activity in list response
├── alembic/
│   └── versions/
│       └── <new>_add_guardian_viewed_at.py  # NEW: migration for the one new column
└── tests/
    ├── unit/
    │   ├── test_mediation_tier.py                    # NEW
    │   └── test_handoff_token.py                     # NEW
    └── integration/
        ├── test_mediation_tier_gating.py             # NEW
        ├── test_guardian_mediation_audit.py          # NEW
        ├── test_guardian_viewed_indicator.py         # NEW
        ├── test_quiz_assignment_start_authorization.py  # MODIFIED: + demo-learner regression
        └── test_answer_read_aloud_logging.py         # NEW (US1)

frontend/
├── src/
│   ├── components/
│   │   ├── QuestionCard.tsx               # MODIFIED: + read-aloud control (Web Speech API)
│   │   └── LearnerAssignments.tsx         # MODIFIED: stores/sends handoff_token,
│   │                                       #           renders unviewed-activity badge
│   ├── lib/
│   │   └── pacing.ts                      # NEW: grade-band -> {recommendedQuestionCount, reinforcementEveryN}
│   └── app/
│       └── quiz/
│           └── quiz-flow.tsx              # MODIFIED: consults pacing.ts, shows stopping-point prompt
└── tests/
    ├── QuestionCard.test.tsx              # MODIFIED
    ├── pacing.test.ts                     # NEW
    └── LearnerAssignments.test.tsx        # MODIFIED

tech-stack.md                              # MODIFIED: one new row, Authentication section
                                            #           (hand-off token as a second JWT purpose)
```

**Structure Decision**: Existing web-application layout (`backend/` +
`frontend/`), unchanged. No new top-level directory, no new deployable
service.

## Complexity Tracking

> Not applicable -- Constitution Check has no violations.
