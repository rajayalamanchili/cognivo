# Implementation Plan: Instructor-Assigned Quizzes

**Branch**: `011-instructor-assigned-quizzes` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-instructor-assigned-quizzes/spec.md`

## Summary

Extends Milestone 5's adaptive-difficulty quiz mechanism so an
instructor can configure and target a quiz assignment (topic(s),
question count, optional due date) at a chosen subset (or all) of a
roster's enrolled learners, and see per-student results in the
instructor dashboard. Introduces two new tables (`quiz_assignments`,
`quiz_assignment_targets`) as a pure join layer on top of the existing,
entirely-unmodified `QuizSession`/`GeneratedQuestion`/grading/mastery-
update mechanism (research.md §1) -- no new grading or difficulty logic
anywhere. Because no real-learner-facing login exists yet (only
guardian and instructor sessions, Milestone 7), a targeted learner's
attempt is started and continued from their own guardian's session
(spec.md Clarifications; research.md §2), a real, if minimal, new
authorization boundary rather than a UI-only feature.

## Technical Context

**Language/Version**: Python 3.12 backend (unchanged), TypeScript/
Next.js frontend (unchanged) -- no new deployable unit.

**Primary Dependencies**: None new. Reuses `services/quiz/session.py`'s
existing `start_quiz`/`generate_quiz_question`/`compute_quiz_summary`
functions and `services/auth/dependencies.py`'s existing
`current_guardian`/`current_instructor`/`current_session_claims`.

**Storage**: PostgreSQL via Neon, same database as every other
milestone. Two new tables (`quiz_assignments`, `quiz_assignment_
targets`) -- see data-model.md. One new Alembic migration. No existing
table altered.

**Testing**: `pytest` (`backend/tests/{unit,integration}/`) for
assignment creation/targeting (empty-target rejection FR-003,
cross-tenant rejection FR-004, snapshot-not-retroactive FR-005),
guardian-mediated start/continue authorization (own-learner-only,
not-targeted rejection, FR-006/FR-013), single-attempt and due-date
enforcement under the DB unique constraint (FR-014, including a
concurrent-double-start race test mirroring
`test_roster_duplicate_join.py`'s existing pattern), unenrollment
blocking a not-yet-started target (FR-011), cancellation leaving
recorded mastery data untouched (FR-012, asserting `MasteryState`/
`AssessmentEvent` rows are byte-for-byte unchanged before/after), and a
regression test asserting an assigned quiz's difficulty-adaptation and
grading behavior is identical to `test_quiz_difficulty_bounds.py`/
`test_quiz_mastery_effect.py`'s existing non-assigned-quiz assertions
run against the same scripted answer sequence (SC-002's hard gate).
`Vitest` + React Testing Library for the new assignment-creation form
(instructor) and assignment-list/start UI (guardian). `Playwright`
(E2E) extends `instructor-classroom-round-trip.spec.ts`'s pattern with
an assign -> guardian-starts -> completes -> instructor-views-per-
student-result round trip.

**Target Platform**: The existing `backend/`+`frontend/` Vercel
Services project -- no new deployable unit.

**Project Type**: Web application (unchanged two-project structure).

**Performance Goals**: Assignment creation and the per-assignment
instructor report load within the same 5-second budget Milestone 7's
dashboard already targets for a 30-learner roster (`instructor_
dashboard.py`'s existing precedent) -- the per-assignment report is a
single joined query across at most `roster_size` target rows, no
per-learner fan-out call.

**Constraints**: The guardian-ownership check added to the two existing
quiz-continuation routes (research.md §2) MUST NOT change their
behavior for a `QuizSession` that isn't assignment-linked -- Milestone
5's existing demo/capability-URL quiz flow is a hard regression
boundary, not just a nice-to-have (SC-002).

**Scale/Scope**: 2 new tables, 6 new API routes (create/list/get/cancel
assignment, list a learner's assignments, start an assignment attempt),
2 extended existing routes (added authorization branch only), new
frontend UI in the existing instructor roster-management page and
guardian learner-management page (no new top-level frontend section).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1
design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | Not implicated -- no mastery-model/Sequencing code touched. | N/A |
| II. Generated content graded against a rubric | Not implicated -- assigned-quiz questions are generated and graded via Milestone 5/6's existing, unmodified mechanism (research.md §1); no new generation or grading path. | N/A |
| III. One engine, many subjects | `QuizAssignment.subject_id`/`topic_ids` are DB values validated at query time against `Topic`/`Subject` rows, never hardcoded -- covered by the existing `check_no_subject_conditionals.py` scan. | PASS |
| IV. Agent boundaries reflect real responsibility | No new or modified agent. Per-assignment reporting is a direct query, deliberately not routed through the Recommendation Agent (research.md §5) -- a different concern than that agent owns, not a duplicated implementation of what it already does. | PASS |
| V. Logged and explainable | Every assignment attempt is an ordinary, already-logged `QuizSession`/`AssessmentEvent` trail (Milestone 5/6, unchanged) linked via `quiz_assignment_targets` -- "why was this learner assigned this" is answerable from `QuizAssignment.instructor_id`/`created_at`, "why was this graded this way" from the same rubric-based mechanism every other quiz question already uses. | PASS |
| VI. A2A justified by concrete need | Not implicated -- no new agent or service boundary. | N/A |
| VII. Spec before code | Full lifecycle followed: Milestone 7 (approved, merged, staging+main) -> this spec (2 clarifications resolved) -> this plan. | PASS |
| VIII. No real learner data | Targets real (`is_demo: false`) `LearnerProfile` rows already gated in by Milestone 7 -- this feature adds no new account-shaped table (`quiz_assignments`/`quiz_assignment_targets` carry no `is_demo` column, matching `Enrollment`'s precedent of not needing one since it isn't itself an account). Guardian-mediated access (research.md §2) is a stricter authorization boundary than Milestone 5's original demo-only quiz flow, not a weaker one. | PASS |
| IX. Deployable and demoable | No new deployable unit; due-date enforcement is a plain per-request timestamp comparison, no assumed persistent process (research.md §3), consistent with Vercel's stateless execution model. | PASS |
| X. Staged release discipline | Feature branch `011-instructor-assigned-quizzes` (rebased onto `origin/staging`) -> PR into `staging`, same as every prior feature. | PASS |

No violations requiring Complexity Tracking.

**Post-Phase-1 re-check**: Phase 1 design (data-model.md, contracts/
api.md) did not surface any new violation or required correction to
the table above -- the two new tables stayed a pure join layer as
planned in research.md §1, and the guardian-auth extension to the two
existing quiz routes (research.md §2) is additive/conditional, not a
behavior change for the existing non-assignment quiz path. Constitution
Check table above still holds unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/011-instructor-assigned-quizzes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md            # Phase 1 output
└── tasks.md               # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── quiz_assignment.py         # NEW
│   │   └── quiz_assignment_target.py  # NEW
│   ├── services/
│   │   └── quiz_assignment/           # NEW
│   │       └── assignment.py          # create/cancel/target-resolution (FR-001-FR-005),
│   │                                     # start-eligibility checks (FR-006/FR-011/FR-014)
│   │                                     # -- calls services/quiz/session.py's existing
│   │                                     # start_quiz()/generate_quiz_question() unchanged
│   └── api/routes/
│       ├── quiz_assignments.py        # NEW -- instructor create/list/get/cancel,
│       │                                 # guardian list/start (contracts/api.md)
│       ├── quiz.py                    # EXTENDED -- next-question route gains the
│       │                                 # conditional guardian-ownership check
│       │                                 # (research.md §2)
│       └── questions.py               # EXTENDED -- answer route gains the same check
├── alembic/versions/
│   └── <new>_instructor_assigned_quizzes.py  # NEW -- quiz_assignments,
│                                                # quiz_assignment_targets
└── tests/
    ├── unit/
    │   └── test_quiz_assignment_target_resolution.py   # NEW
    └── integration/
        ├── test_quiz_assignment_create.py               # NEW
        ├── test_quiz_assignment_start_authorization.py   # NEW
        ├── test_quiz_assignment_single_attempt.py        # NEW
        ├── test_quiz_assignment_due_date.py              # NEW
        ├── test_quiz_assignment_cancellation.py          # NEW
        ├── test_quiz_assignment_unenrollment.py           # NEW
        └── test_quiz_assignment_mastery_parity.py         # NEW -- SC-002's hard gate

frontend/
└── src/app/
    ├── instructor/rosters/
    │   └── rosters-flow.tsx           # EXTENDED -- add "assign a quiz" action per
    │                                     # roster and a per-assignment results view
    └── (auth)/guardian/learners/
        └── page.tsx                   # EXTENDED -- list a learner's assignments and
                                          # a "start" action, reusing the existing
                                          # quiz-flow.tsx question/answer UI
```

**Structure Decision**: Extends the existing two-project (`backend/`,
`frontend/`) structure -- no new deployable unit, no new top-level
frontend route. New backend code follows the same `models/`,
`services/<concern>/`, `api/routes/` organization every prior milestone
has used; `services/quiz_assignment/` stays a thin layer that calls
into `services/quiz/session.py` rather than reimplementing any of it,
directly reflecting research.md §1's structural guarantee.

## Complexity Tracking

No violations -- table not needed.
