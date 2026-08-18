# Implementation Plan: Learner Dashboard

**Branch**: `004-learner-dashboard` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-learner-dashboard/spec.md`

## Summary

The Learner Dashboard is a read-time composition, not a new source of
truth: for every subject with a validated content artifact, it renders
one section combining (a) Milestone 1's existing per-topic mastery view,
(b) a fresh, subject-scoped call to the Recommendation Agent's existing
weak-area endpoint, and (c) a new, lightweight preview of the Sequencing
Agent's current topic-priority ranking (the same deterministic ranking
`select_next_topic` already computes, exposed one layer further so the
dashboard can show the next topic plus up to 3 likely-upcoming ones
without generating an actual question). Per this feature's
Clarifications, the three pieces are fetched independently per subject
so a failure in one (most likely the new preview call) never blocks the
other two from rendering. No new agent, no new LLM/ADK call, and no new
persisted entity -- `DashboardView` (spec.md Key Entities) is assembled
fresh on every request from existing tables plus two thin new
read-only endpoints.

## Technical Context

**Language/Version**: Python 3.12 (backend, matches `backend/pyproject.toml`) + TypeScript/Next.js (frontend, matches `frontend/package.json`) -- this is the first feature since Milestone 1 to touch both.

**Primary Dependencies**: Backend -- FastAPI, SQLAlchemy 2.0, Pydantic 2 (all already locked, no new dependency). Frontend -- Next.js, React, Tailwind (all already locked, no new dependency).

**Storage**: PostgreSQL via Neon (existing schema, read-only for this feature) -- reads `Subject`, `Topic`, `PrerequisiteEdge`, `MasteryState`; the reused `/recommendations` call also reads/writes `AssessmentEvent` exactly as it already does (unchanged). No migration.

**Testing**: `pytest` (backend, `backend/tests/{unit,integration}/`) for the two new endpoints and the topic-priority-ranking refactor; `Vitest` + React Testing Library (frontend component tests) for per-subject-section rendering and failure-isolation states; `Playwright` (E2E) for the multi-subject dashboard load, per `tech-stack.md`.

**Target Platform**: Same deployed Vercel Services project (FastAPI ASGI backend + Next.js frontend) as Milestones 1-2 -- two new backend routes mounted on the existing `app`, one new Next.js route (`/dashboard`). No new deployment unit.

**Project Type**: Web service (existing `backend/` + `frontend/` monorepo). This is the first Learner-Dashboard-specific frontend work; it reuses the existing `MasteryView` component as-is for FR-001 (see research.md §1) and adds new components for the weak-area and path-visualization sections.

**Performance Goals**: No SC in spec.md states a latency target. Per subject section, the dashboard issues 3 small, already-indexed reads (mastery-state, recommendations, topic-priority-preview); for the current 2-subject platform that's 6 total calls per dashboard load, well within Vercel's default Function execution window (same conclusion as spec 002's research.md §-equivalent judgment, restated here since this feature multiplies the call count by subject count for the first time).

**Constraints**: Stateless per request (no dashboard-level cache, per Constitution Principle IX / FR-006) -- every load recomputes from Postgres and re-calls the Recommendation Agent fresh, per subject.

**Scale/Scope**: Single learner per dashboard load (spec.md Assumptions); all subjects with a validated content artifact in the platform (currently `algebra-1`, `biology`) rendered simultaneously, per this feature's Clarifications.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | The path visualization's "next topic" and "upcoming topics" are both read directly from the Sequencing Agent's existing deterministic `select_next_topic` ranking (extended to expose more of the same ranked list, not a new algorithm) -- see research.md §1. No LLM involved anywhere in this feature. | PASS |
| II. Generated content graded against a rubric | N/A -- this feature generates no assessment questions. | N/A |
| III. One engine, many subjects | Every new read (subjects list, topic-priority-preview) is parameterized by `subject_id` with no subject-id-keyed conditional, covered by the existing `check_no_subject_conditionals.py` scan. | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent. The new topic-priority-preview logic is an extension of the existing Sequencing Agent's own responsibility (topic ranking), not a new boundary -- consistent with `CLAUDE.md`'s explicit note that this milestone does not introduce a new agent. | PASS |
| V. Logged and explainable | FR-002's weak-area section is logged exactly as today (`/recommendations`' existing `AssessmentEvent` writes, unchanged). The new topic-priority-preview call is deliberately **not** logged as a `next_topic_selected` audit event and emits no Langfuse span -- see research.md §3 for why treating an unrequested, illustrative dashboard preview as a real "why was I shown this" decision would misrepresent Principle V rather than satisfy it. | PASS |
| VI. A2A justified by concrete need | No new agent boundary introduced (see Principle IV row); N/A. | N/A |
| VII. Spec before code | This plan follows the approved, clarified spec.md (Clarifications session 2026-08-17). | PASS |
| VIII. No real learner data | Reads only `DemoLearnerProfile`-scoped rows, same as Milestones 1-2. No new learner-data surface. | PASS |
| IX. Deployable and demoable | Two new routes mount on the already-deployed FastAPI app; one new Next.js route on the already-deployed frontend. No new deployment unit or persistent-process assumption. | PASS |
| X. Staged release discipline | Feature branch `004-learner-dashboard` -> PR into `staging`, per existing workflow. | PASS (process, not a design gate) |

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/004-learner-dashboard/
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
│   ├── agents/
│   │   └── sequencing/
│   │       └── agent.py           # + preview_topic_priority(): extracts the
│   │                                # existing eligible/fallback ranking into a
│   │                                # shared private helper reused by both
│   │                                # select_next_topic() (unchanged behavior)
│   │                                # and this new read-only preview
│   └── api/routes/
│       ├── subjects.py             # NEW: GET /api/subjects
│       └── sequencing_preview.py   # NEW: GET /api/learners/{learner_id}/topic-priority-preview
└── tests/
    ├── unit/
    │   └── test_topic_priority_ranking.py   # NEW: pure ranking/upcoming-count logic
    └── integration/
        ├── test_subjects_list.py            # NEW
        ├── test_topic_priority_preview.py   # NEW
        └── test_dashboard_two_subjects.py   # NEW: SC-005 extensibility check, mirrors
                                               # tests/integration/test_second_subject.py

frontend/
├── src/
│   ├── app/
│   │   └── dashboard/
│   │       ├── page.tsx             # NEW
│   │       └── dashboard-flow.tsx   # NEW: fetches per-subject data, one
│   │                                  # independent fetch per section per FR-007/FR-008
│   ├── components/
│   │   ├── DashboardSubjectSection.tsx   # NEW: composes the 3 sections for one subject
│   │   ├── WeakAreaSection.tsx           # NEW: FR-002
│   │   └── PathVisualization.tsx         # NEW: FR-003/FR-004
│   │                                       # (MasteryView.tsx is REUSED unchanged for FR-001)
│   └── services/
│       └── api.ts                   # + getSubjects(), getRecommendations(),
│                                       # getTopicPriorityPreview()
└── tests/
    └── unit/
        └── dashboard-failure-isolation.test.tsx  # NEW: FR-007/FR-008
                                                     # (matches vitest.config.mts's
                                                     # tests/unit/**/*.test.{ts,tsx} glob)
```

**Structure Decision**: Extends the existing `backend/` + `frontend/`
monorepo from Milestones 1-2 -- no new project. Backend follows the
established `agents/<name>/agent.py` (orchestration/ranking) +
`api/routes/<name>.py` (thin HTTP layer) split; frontend follows the
established `app/<route>/page.tsx` + `<route>-flow.tsx` (data fetching)
+ `components/` (presentational) split already used by
`app/mastery/{page,mastery-flow}.tsx` + `components/MasteryView.tsx`.

## Post-Design Constitution Check

*Re-checked after Phase 1 (data-model.md, contracts/api.md,
quickstart.md).* Phase 1 introduced two concrete decisions beyond the
Phase 0 Constitution Check above: (1) `preview_topic_priority` as a
read-only extension of the Sequencing Agent's existing ranking logic,
sharing its query/eligibility helper rather than duplicating it, and
(2) two new thin GET endpoints, neither writing any new row or
requiring a migration. Neither revisits a `tech-stack.md`-locked choice
(framework, database, deployment target, agent boundaries). All ten
principles re-checked above still PASS; no new gate failure.

## Complexity Tracking

*No Constitution Check violations -- table intentionally omitted.*
