# Implementation Plan: Learner-Facing UI Redesign

**Branch**: `037-learner-ui-redesign` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-learner-ui-redesign/spec.md`

## Summary

Restyle the six existing learner-facing screens (Dashboard, Practice, Mastery,
Placement, AI Tutor, Answer Result) to a new purple/lavender visual language
(pill-shaped nav/buttons, 20-24px rounded cards, a refreshed color palette) by
updating the project's existing `globals.css` design-token system and the
Tailwind utility classes each component already uses. No data, logic,
navigation, or API surface changes. Source of truth for the new values is six
static reference mockups exported from Claude Design
(`/home/raja/cognivo_learner_screens/extracted/*/*.dc.html`).

## Technical Context

**Language/Version**: TypeScript, Next.js 16 / React 19 (already locked, `tech-stack.md` Frontend row)

**Primary Dependencies**: Tailwind CSS v4 (`@theme inline` token system in `frontend/src/app/globals.css`), `next/font/google` (Baloo 2 + Nunito, already loaded in `frontend/src/app/layout.tsx`) -- no new dependency

**Storage**: No new table/column/migration. One new read-only query (FR-009) against the existing `AssessmentEvent` table.

**Testing**: Vitest + React Testing Library (existing frontend suite); no new test tooling

**Target Platform**: Web, deployed via Vercel (existing target, unchanged)

**Project Type**: Web application -- frontend-only change within the existing `frontend/` Next.js app

**Performance Goals**: N/A -- purely presentational change, no new runtime work added to any request path

**Constraints**: Zero grading/mastery/sequencing-logic or navigation-target regression (FR-002, FR-003); at most one new read-only backend endpoint, no new table/migration (FR-008/FR-009); demo badge and non-color accessibility cues preserved (FR-004, FR-005)

**Scale/Scope**: 6 page-level components + their shared sub-components (`DashboardSubjectSection`, `MasteryTrend`, `MasteryView`, `TutorChat`, `AnswerResultView`, `Nav`, `DemoBadge`) plus the shared `globals.css` token layer

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Personalization Is a Model, Not a Guess** -- PASS. No mastery-model or sequencing logic touched. FR-009's new endpoint is a plain count query (no model, no inference); Dashboard's "Up next"/refresh-card copy is derived client-side from the Sequencing Agent's own already-computed `topic-priority-preview`/`mastery-state` output, never a new inference.
- **II. Generated Content Graded Against a Rubric** -- N/A. No grading logic touched; `AnswerResultView`'s per-criterion display is restyled, not recomputed.
- **III. One Engine, Many Subjects** -- PASS. No subject-specific conditional is introduced; styling changes are token/component-level and apply uniformly across subjects.
- **IV. Agent Boundaries Reflect Real Responsibility** -- N/A. No agent code touched.
- **V. Every Decision Is Logged and Explainable** -- PASS (preserving, not adding). FR-003 requires the existing "why this question?" / "why was this marked wrong?" UI (spec 025) keep working, restyled only -- no change to what is logged or how it's surfaced. FR-009's endpoint reads the existing audit log read-only; it writes no new event and changes no logging behavior.
- **VI. Agent Boundaries Match Deployment Boundaries** -- N/A. No A2A service touched.
- **VII. Spec Before Code, Milestone-Gated** -- PASS. This plan follows an approved `spec.md`; `/speckit-tasks` and `/speckit-analyze` follow before implementation, per the user's explicit choice to run the full spec-kit lifecycle for this feature.
- **VIII. No Real Learner Data Until Privacy/Retention Specified** -- PASS (preserving). FR-004/SC-003 require the persistent demo-account badge survive the restyle; no new data display is introduced.
- **IX. Deployable and Demoable From the Start** -- PASS. Change is a CSS/component-class update within the existing Next.js app; no new architecture, no new Vercel configuration, no persistent-state assumption introduced.
- **X. Staged Release Discipline** -- PASS. Branch `037-learner-ui-redesign` was cut from `origin/staging`; will PR into `staging` first, same as every other feature.

No violations. Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/027-learner-ui-redesign/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command) -- not applicable, see below
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css              # design-token system -- new palette/radius values land here
│   │   ├── dashboard/dashboard-flow.tsx
│   │   ├── practice/practice-flow.tsx
│   │   ├── mastery/mastery-flow.tsx
│   │   ├── placement/placement-flow.tsx
│   │   └── tutor/tutor-flow.tsx
│   └── components/
│       ├── AnswerResultView.tsx
│       ├── DashboardSubjectSection.tsx
│       ├── MasteryTrend.tsx
│       ├── MasteryView.tsx
│       ├── TutorChat.tsx
│       ├── Nav.tsx
│       └── DemoBadge.tsx
└── tests/                           # existing Vitest suite, unchanged in behavior-under-test
```

**Structure Decision**: Primarily a styling-layer change confined to the token
definitions in `globals.css` and the six flow components plus their shared
sub-components listed above, within the existing `frontend/` Next.js app. One
narrow backend addition (Clarifications, second pass; FR-009): a new route
`backend/src/api/routes/activity_summary.py` (`GET /api/learners/{id}/
activity-summary`), registered in `backend/src/api/main.py`, following the
existing `sequencing_preview.py`/`mastery.py` read-only-GET pattern exactly --
no new model, no migration. No `contracts/` artifact applies beyond this one
endpoint, documented inline in its route file per this project's existing
convention (no dedicated `contracts/` directory is used elsewhere in this
codebase either). Phase 1 produces `data-model.md` (documenting that no new
entity exists) and `quickstart.md` (a visual-comparison + regression-test
validation guide).

## Complexity Tracking

*No Constitution Check violations -- table not needed.*
