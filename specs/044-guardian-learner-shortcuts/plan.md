# Implementation Plan: Guardian Multi-Subject Cards & Practice/Tutor Shortcuts

**Branch**: `044-guardian-learner-shortcuts` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/044-guardian-learner-shortcuts/spec.md`

## Summary

Six small, independently-testable additions on top of spec 041's guardian
experience: (1) a learner's card on Guardian · My learners shows every
enrollment, not just one, with tabs to switch and an "Add a subject"
action available regardless of how many a learner already has; (2) each
subject tile gets a "Start practice" shortcut straight into a running
15-minute timed session; (3) Practice's "Ask the AI Tutor" links open an
inline, collapsible side-panel chat on Practice itself instead of
navigating to `/tutor`; (4) wherever the Tutor's suggested-prompt pills
render, their wording reflects the learner's current topic instead of
generic text, and Dashboard's own Tutor link becomes subject-scoped; (5) a
"Take placement" shortcut lets a guardian get a learner a real starting
grade, reversing spec 041's "real placement stays demo-only" decision as
a fully optional fast-track; (6) leaving Practice or Placement mid-question
via in-app navigation shows a warning first, since neither page persists
an in-progress question today.

Two of these (2 and 5) depend on a pre-existing gap found during
`/speckit-clarify`, not scoped at `/speckit-specify` time: the timed
practice-session endpoints (`practice_sessions.py`) and `start_placement`
(`placement.py`) are both hardcoded to the demo learner, the exact same
gap class spec 041 already closed for `next-question`/`mastery-state`/
etc. but never touched for these two. Both get the identical fix: accept
a real `learner_id`, gated with `require_learner_ownership_if_real`
(`services/auth/dependencies.py`), mirroring `get_next_question`'s own
`has_placement_data` bypass for a non-demo real learner exactly.

Zero new third-party dependency. **Zero new database tables or columns**
-- every entity this feature touches (`Enrollment`, `PracticeSession`,
`GradeProgress`, `QuizAssignment`) already has the shape it needs; this is
a response-shape, gating, and frontend-layout feature throughout.

## Technical Context

**Language/Version**: TypeScript (Next.js 16.3.1 / React 19.2.8) for frontend, Python (FastAPI) for backend -- both already locked, `tech-stack.md` Frontend/Backend rows

**Primary Dependencies**: None new. Reuses `services/auth/dependencies.py`'s `require_learner_ownership_if_real`/`optional_session_claims` (real-learner gating), `lib/visitor-state.ts`'s localStorage+subscriber pattern (for Story 6's leave-guard, same shape as the existing demo/real-learner session state), and `TutorChat.tsx` as-is (Story 3 mounts it inline instead of building a new chat UI)

**Storage**: PostgreSQL via Neon (existing). Zero new tables, zero new columns -- `Enrollment.UniqueConstraint("learner_id", "roster_id")` already supports multiple enrollments per learner (Story 1); `PracticeSession`/`GradeProgress` already have a real `learner_id` FK, just never reached by a non-demo caller today (Stories 2/5)

**Testing**: `pytest` (backend), `Vitest` + React Testing Library (frontend), `Playwright` (e2e) -- existing suites extended, no new tooling

**Target Platform**: Web, deployed via Vercel (existing target, unchanged)

**Project Type**: Web application -- both `frontend/` and `backend/` touched

**Performance Goals**: N/A beyond what already-reused endpoints meet. The two real-learner-gating additions (Stories 2, 5) add one `require_learner_ownership_if_real` DB lookup per call, the same cost every other real-learner-ownership-gated route (`next-question`, `mastery-state`, etc.) already pays.

**Constraints**: Zero mastery/grading/sequencing-logic change (spec FR-025's `determine_starting_grade` reuse, FR-010's "identical in every other respect" session behavior); placement MUST stay fully optional, never gating Practice/Dashboard/Mastery/quizzes (FR-027); Story 6's warning covers in-app navigation only, no native `beforeunload` handler (FR-031); "assigned quizzes... switch per tab" (spec FR-002) requires a small, previously-unscoped backend addition -- `GET /api/learners/{learner_id}/assignments` has no subject/roster filter today even though `QuizAssignment.roster_id` already exists, so every assignment across every enrollment shows on every tab unless filtered (see research.md)

**Scale/Scope**: 1 backend response-shape change (`GET /api/learners/mine`), 2 backend endpoints gaining real-learner support (`start_practice_session` + 3 siblings, `start_placement`), 2 small backend additions not previously called out at spec time (`roster_id` filter on `GET /api/learners/{learner_id}/assignments`; `has_starting_grade` field on `GET /api/learners/{learner_id}/enrollments`), ~9 frontend files changed (`GuardianLearnerCard.tsx`, the guardian learners page, the guardian settings page, `GuardianLearnerStandards.tsx`, `GuardianLearnerCareerConnections.tsx`, `LearnerAssignments.tsx`, `practice-flow.tsx`, `tutor-flow.tsx`/`TutorChat.tsx`, `DashboardSubjectSection.tsx`, `Nav.tsx`), 1 new shared frontend module (a leave-guard hook for Story 6), zero new/changed migrations

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Personalization Is a Model, Not a Guess** -- PASS. No mastery-model or sequencing logic touched. Story 5 reuses `determine_starting_grade`'s existing deterministic computation verbatim for a real `learner_id`; Story 2 reuses the existing timed-session mechanic verbatim. Neither introduces a new personalization decision.
- **II. Generated Content Graded Against a Rubric** -- N/A. No grading logic touched anywhere in this feature.
- **III. One Engine, Many Subjects** -- PASS. No subject-id-keyed conditional introduced. Story 4's topic-worded prompts are a client-side template substitution of an already-fetched, subject-agnostic `topic.display_name`, not subject-specific logic.
- **IV. Agent Boundaries Reflect Real Responsibility** -- N/A. No agent code touched; Story 3 mounts the existing `TutorChat.tsx`/Tutor Agent integration in a new location, with zero change to the agent boundary or its A2A call.
- **V. Every Decision Is Logged and Explainable** -- PASS (preserving). Story 5's placement-assigned starting grade is logged via the exact same `AssessmentEventType.GRADE_ASSIGNED` audit event `_assign_starting_grade_if_graded` already writes for the demo learner -- no new logging path, no logging path removed.
- **VI. Agent Boundaries Match Deployment Boundaries** -- N/A. No A2A service touched.
- **VII. Spec Before Code, Milestone-Gated** -- PASS. This plan follows an approved `spec.md` (6 user stories, 33 functional requirements, all `/speckit-clarify` rounds resolved with zero open `[NEEDS CLARIFICATION]` markers); `/speckit-tasks` and `/speckit-analyze` follow before implementation.
- **VIII. No Real Learner Data Until Privacy/Retention Specified** -- PASS. Privacy/retention was specified at spec 009/Milestone 7. Stories 2 and 5 extend *which already-authorized real learners* can reach already-existing real-data endpoints and mechanisms (their own guardian's own learners, via the existing `require_learner_ownership_if_real` gate) -- no new category of data is collected, and no demo-account flag/badge discipline is touched.
- **IX. Deployable and Demoable From the Start** -- PASS. All changes are within the existing Next.js/FastAPI/Vercel architecture. Zero new migration, so no new per-environment migration step is introduced.
- **X. Staged Release Discipline** -- PASS. Branch `044-guardian-learner-shortcuts` was cut from `origin/staging`; will PR into `staging` first, same as every other feature.

No violations. Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/044-guardian-learner-shortcuts/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── api-changes.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/routes/
│   │   ├── learners.py                   # MyLearnerOut.enrollment -> enrollments: list[...]
│   │   │                                  #   (FR-001); every roster returned, not just one
│   │   ├── practice_sessions.py          # start_practice_session/get_practice_next_question/
│   │   │                                  #   end_practice_session/get_practice_session_summary
│   │   │                                  #   each gain `learner_id`, gated with
│   │   │                                  #   require_learner_ownership_if_real + the same
│   │   │                                  #   has_placement_data bypass next-question already
│   │   │                                  #   has for a non-demo real learner (FR-008)
│   │   ├── placement.py                  # start_placement gains `learner_id`, identical
│   │   │                                  #   gating pattern (FR-025); submit_placement/
│   │   │                                  #   skip_placement_question unchanged (already
│   │   │                                  #   learner-agnostic -- derive learner_id from the
│   │   │                                  #   GeneratedQuestion row)
│   │   ├── quiz_assignments.py           # list_learner_assignments_route gains an optional
│   │   │                                  #   `roster_id` query param, filtering
│   │   │                                  #   QuizAssignment.roster_id (research.md) --
│   │   │                                  #   closes a gap FR-002 implies but didn't name
│   │   └── rosters.py                    # list_learner_enrollments_route's LearnerEnrollmentOut
│   │                                      #   gains `has_starting_grade: bool` (FR-024),
│   │                                      #   same no-second-round-trip precedent
│   │                                      #   is_default_instructor_roster already set
│   └── services/demo_learner.py          # unchanged -- demo path stays the default fallback
│                                          #   everywhere a learner_id param is now optional
└── tests/
    ├── integration/test_my_learners.py           # new -- multi-enrollment response shape
    │                                              #   (no backend/tests/api/ dir in this repo;
    │                                              #   real convention is integration/+contract/)
    ├── contract/test_practice_session_*.py       # extend existing files -- real-learner
    │                                              #   start/resume/gating cases
    ├── integration/test_placement.py             # extend existing -- real-learner start case
    ├── integration/test_quiz_assignment_roster_filter.py  # new -- roster_id filter case
    └── integration/test_learner_enrollments.py   # extend existing -- has_starting_grade field

frontend/
├── src/
│   ├── lib/
│   │   └── leave-guard.ts                # NEW -- tiny shared module (same localStorage-free,
│   │                                      #   subscriber-callback shape as visitor-state.ts,
│   │                                      #   but in-memory only: a guard is only ever live
│   │                                      #   within the current page's lifetime) backing
│   │                                      #   Story 6; set/cleared by practice-flow.tsx and
│   │                                      #   placement-flow.tsx, read by Nav.tsx and
│   │                                      #   practice-flow.tsx's own "End session" link
│   ├── components/
│   │   ├── GuardianLearnerCard.tsx       # single `enrollment` prop -> `enrollments: [...]`
│   │   │                                  #   list; tab row (FR-002/FR-005); "Add a subject"
│   │   │                                  #   shown unconditionally (FR-003); "Start practice"
│   │   │                                  #   (FR-007) and "Take placement" (FR-024) tile
│   │   │                                  #   actions
│   │   ├── GuardianLearnerStandards.tsx  # + optional `subjectId` filter prop (FR-002 scopes
│   │   │                                  #   standards to the selected tab, not every subject
│   │   │                                  #   combined)
│   │   ├── GuardianLearnerCareerConnections.tsx  # same `subjectId` filter addition
│   │   ├── LearnerAssignments.tsx        # + optional `rosterId` prop, threaded into
│   │   │                                  #   listLearnerAssignments's new query param
│   │   ├── TutorChat.tsx                 # SUGGESTED_PROMPTS becomes a function of an
│   │   │                                  #   optional `currentTopicDisplayName` prop
│   │   │                                  #   (FR-020/FR-021), falling back to today's
│   │   │                                  #   generic wording when absent
│   │   ├── Nav.tsx                       # DashboardSubjectSection's Tutor link gains
│   │   │                                  #   `?subject=`; leave-guard check wraps every
│   │   │                                  #   bucket's nav links + the real-learner banner's
│   │   │                                  #   "Exit learner view"/"End session" actions
│   │   └── LeaveGuardDialog.tsx           # NEW -- the shared confirmation modal (Story 6),
│   │                                      #   rendered once near the app root, driven by
│   │                                      #   leave-guard.ts's subscriber state
│   ├── app/
│   │   ├── (auth)/guardian/
│   │   │   ├── learners/page.tsx         # passes enrollments (plural) through to the card
│   │   │   └── settings/page.tsx         # per-learner summary line becomes multi-subject-
│   │   │                                  #   aware (mirrors GuardianLearnerCard's own
│   │   │                                  #   `summary` computation, not duplicated logic)
│   │   ├── practice/practice-flow.tsx    # registers/clears the leave guard on phase change;
│   │   │                                  #   "Ask the AI Tutor" links become an inline
│   │   │                                  #   collapsible side panel mounting TutorChat.tsx
│   │   │                                  #   (FR-012/FR-013), with an auto-sent hint message
│   │   │                                  #   (FR-014/FR-015); supports an `autostart` mode
│   │   │                                  #   for Story 2's shortcut (skips the picker phase)
│   │   ├── placement/placement-flow.tsx  # registers/clears the leave guard while any shown
│   │   │                                  #   question is unsubmitted
│   │   └── tutor/tutor-flow.tsx          # reads `?subject=` to skip the picking phase
│   │                                      #   (FR-020); passes the active topic's display
│   │                                      #   name into TutorChat for prompt wording
│   └── components/DashboardSubjectSection.tsx  # "Ask the AI Tutor first" link gains
│                                          #   `?subject=${subjectId}` (FR-020)
└── tests/
    ├── unit/
    │   ├── guardian-learners.test.tsx        # + multi-enrollment tab rendering/switching
    │   ├── guardian-learner-standards.test.tsx  # + subjectId filter case
    │   ├── practice-flow.test.tsx            # + inline tutor panel, autostart, leave-guard
    │   ├── tutor-chat.test.tsx               # + topic-worded suggested prompts
    │   ├── nav.test.tsx                      # + leave-guard interception, `?subject=` link
    │   └── leave-guard.test.ts               # NEW -- the shared module's own small test
    └── e2e/
        └── tutor-round-trip.spec.ts          # + inline-panel hint flow, if end-to-end
                                               #   coverage is warranted (tasks.md decides)
```

**Structure Decision**: Existing `backend/` (FastAPI) + `frontend/` (Next.js) web-application
structure, unchanged. No new top-level directory, no new service, no new
deployment target -- every file above already exists except `leave-guard.ts`
and `LeaveGuardDialog.tsx` (Story 6's small, self-contained addition).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations -- table not needed.
