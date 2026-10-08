# Implementation Plan: Instructor-Facing UI Redesign and Default-Instructor Self-Service

**Branch**: `043-instructor-ui-redesign` | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/043-instructor-ui-redesign/spec.md`

## Summary

Two parts sharing one spec. (1) Restyle the existing Dashboard, Review,
and Rosters instructor screens to match four provided mockups, and add
a new instructor Settings screen (password change, display/notification
preferences, classroom defaults, deletion-request entry points, demo
badge) -- almost entirely built by mirroring patterns the guardian side
already shipped (spec 041): `RealGuardianAccount`'s password-change
endpoint and theme/larger-text/reduce-motion columns get instructor
equivalents; `POST /api/deletion-requests` is reused completely
unchanged. (2) Seed a real (non-demo) "default instructor" account that
always owns one open, listed `ClassroomRoster` per `Subject`, so a
guardian can enroll a learner and self-assign a quiz for any subject
even with zero real instructors ever registering -- this reuses the
guardian class directory (spec 041) and roster/quiz-assignment services
completely unchanged, adding exactly one new, narrowly-scoped
guardian-facing endpoint for self-assignment.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript (Next.js
frontend) -- both already locked, no change.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, `argon2-cffi`
(backend); Next.js, React (frontend) -- all already locked
(`tech-stack.md`). No new dependency introduced by this feature.

**Storage**: PostgreSQL via Neon (already locked). This feature adds
columns to the existing `real_instructor_accounts` table only -- no new
table.

**Testing**: `pytest` (backend), `Vitest` + React Testing Library
(frontend) -- already locked, no change.

**Target Platform**: Vercel (Services: `frontend` + `backend`) --
already locked, no change. The new seed script
(`backend/scripts/seed_default_instructor.py`) follows the exact
precedent of the already-existing `seed_demo_instructor.py` and
`load_content_artifact.py`: a manually-run, idempotent script against a
target environment's `DATABASE_URL`, not a Vercel Cron job or build
hook -- no persistent process, consistent with Constitution Principle
IX.

**Project Type**: Web application (`backend/` + `frontend/`, Vercel
Services) -- already locked.

**Performance Goals**: No new performance target beyond this project's
existing per-request guardrails; every new endpoint is a simple CRUD
read/write with no LLM call, no different latency profile than
`PATCH /api/auth/guardian/me` or `POST /api/rosters/{roster_id}/
assignments`, both already in production.

**Constraints**: Vercel's stateless, ephemeral serverless execution
model (already locked) -- no new background process, no new cron job.
The default instructor's real credentials MUST be supplied via
environment variables, never committed (spec.md FR-020).

**Scale/Scope**: Three existing screens restyled, one new screen, one
new seed script, one new narrowly-scoped backend endpoint, one small
additive field on an existing endpoint, eight new columns on
`RealInstructorAccount`, zero new tables, zero new external
dependencies.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | No mastery-model or sequencing change. | PASS (N/A) |
| II. Generated Content Graded Against a Rubric | No grading/question-generation change. | PASS (N/A) |
| III. One Engine, Many Subjects | FR-016's new-subject default-roster seeding iterates every `Subject` row generically (no subject-id-keyed conditional); verified at Phase 1 design time, re-verified by `check_no_subject_conditionals`-style review at `/speckit-analyze`. | PASS |
| IV. Agent Boundaries Reflect Real Responsibility | No agent touched -- this feature is entirely auth/roster/settings/UI work. | PASS (N/A) |
| V. Every Decision Logged and Explainable | The new guardian-facing quiz-assignment endpoint reuses `create_assignment()` unchanged, so it emits the same `QUIZ_ASSIGNMENT_CREATED` audit event with the same `instructor_id` (the default instructor's) regardless of which session (guardian or instructor) triggered it -- no new, differently-shaped audit path. Deletion requests already audited by spec 020, reused as-is. | PASS |
| VI. Agent Boundaries Match Deployment Boundaries | No new A2A service. | PASS (N/A) |
| VII. Spec Before Code, Milestone-Gated | This plan follows an approved, clarified `spec.md`; `tasks.md` and `/speckit-analyze` follow before `/speckit-implement`. Tracked as `roadmap.md` Milestone 25. | PASS |
| VIII. No Real Learner Data Until Privacy/Retention Specified | The default instructor is a real, non-demo `RealInstructorAccount` row (FR-019) -- the same account *type* already permitted since Milestone 7/spec 009, just operator-seeded rather than self-registered. No new real-minor data category is introduced; existing deletion-request authorization (spec 020) already covers both targets this feature exposes UI for. | PASS |
| IX. Deployable and Demoable From the Start | No new persistent process; the seed script is a manual, idempotent step against Vercel-hosted Postgres, matching existing precedent (`seed_demo_instructor.py`). | PASS |
| X. Staged Release Discipline | Work lands on `043-instructor-ui-redesign`, PR'd into `staging`, promoted to `main` via a separate PR, per existing workflow. | PASS (process, not a design gate) |

No violations. Complexity Tracking table is not needed.

**Post-Phase-1 re-check**: Design artifacts (research.md,
data-model.md, contracts/, quickstart.md) confirm no new table, no new
A2A boundary, no new subject-id-keyed conditional (FR-016's seeding
helper iterates `Subject` rows generically), and no new external
dependency -- all ten rows above still hold unchanged after design.

## Project Structure

### Documentation (this feature)

```text
specs/043-instructor-ui-redesign/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   └── api-changes.md
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── real_instructor_account.py      # extended: 8 new columns
│   ├── api/routes/
│   │   ├── auth.py                          # extended: instructor /me, new change-password
│   │   └── rosters.py                       # extended: one new guardian-facing assignment route,
│   │                                         #   one additive field on learner-enrollments response
│   └── services/
│       └── roster/
│           └── default_instructor.py        # NEW: get_default_instructor(), ensure_default_instructor_roster_for_subject()
├── scripts/
│   ├── seed_default_instructor.py           # NEW: idempotent seed, mirrors seed_demo_instructor.py
│   └── load_content_artifact.py             # extended: calls ensure_default_instructor_roster_for_subject()
├── alembic/versions/
│   └── <new>_instructor_preferences_and_defaults.py   # NEW migration
└── tests/
    ├── unit/ (new: default_instructor service tests)
    └── integration/ (extended: instructor settings, guardian self-assignment)

frontend/
├── src/
│   ├── app/
│   │   ├── instructor/
│   │   │   ├── dashboard/, review/, rosters/   # restyled in place
│   │   │   └── settings/                       # NEW page
│   │   └── (auth)/guardian/learners/            # extended: "assign a quiz" action on a
│   │                                             #   default-instructor-owned enrollment card
│   └── components/
│       ├── AccountDisplayPreferences.tsx        # extended: instructor branch, not guardian-only
│       └── InstructorSettingsFlow.tsx           # NEW (or inline in settings/page.tsx per existing convention)
└── tests/ (extended: Vitest coverage for the new Settings screen and the guardian assignment action)
```

**Structure Decision**: Existing Option 2 (web application: `backend/`
+ `frontend/`, both Vercel Services) -- no structural change. Every new
file sits inside an existing directory using this project's established
per-feature-area convention (routes in `api/routes/`, business logic in
`services/<area>/`, scripts in `scripts/`), matching exactly how spec
041 added its own guardian-facing settings/directory code.

## Complexity Tracking

*No violations -- table not needed.*
