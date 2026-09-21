# Implementation Plan: Real-Account Deletion Pathway

**Branch**: `030-deletion-pathway` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/020-deletion-pathway/spec.md`

## Summary

Makes spec 009's already-approved FR-004 (deletion request), FR-005
(cascade), and FR-010 (1-year post-inactivity auto-deletion) actually
execute, against the `DeletionRequest`/`RetentionRecord` models
Milestone 7 created but never wired to a working deletion mechanism.
Two new endpoints (`POST`/`GET /api/deletion-requests`) let a guardian
or instructor submit and check on a deletion request; a new Vercel Cron
job (`/api/cron/execute-deletions`, same auth pattern as the existing
`reset-demo-data`/`classify-misconceptions` crons) both sweeps
`RetentionRecord`s past the 1-year inactivity ceiling and executes
pending requests via an explicit, transaction-wrapped, dependency-order
delete across the existing FK graph (`data-model.md`). No new tables,
no new columns, no new agent.

## Technical Context

**Language/Version**: Python 3.12 (`backend/`) -- unchanged, no new runtime

**Primary Dependencies**: FastAPI, SQLAlchemy/Alembic (existing) -- this feature adds zero new dependencies

**Storage**: PostgreSQL via Neon (existing). Zero new tables, zero new columns -- reuses `DeletionRequest`/`RetentionRecord` exactly as spec 009 defined them

**Testing**: `pytest` (`backend/`) -- unchanged framework, new test cases only

**Target Platform**: Vercel serverless (existing `backend` Service) -- one new cron path added to `vercel.json`'s existing `crons` array, no new deployable, no `maxDuration` override

**Project Type**: Web application (existing `backend` + `frontend`), per `tech-stack.md`'s locked Vercel Services structure. No frontend change is required for this milestone's compliance gate -- the submission/status endpoints are usable via API today; a guardian/instructor-facing UI for them is not part of this milestone's Definition of Done (spec.md does not name one)

**Performance Goals**: Every `DeletionRequest` completes within the existing 30-day SLA (spec 009 FR-004); the cron executor's per-run batch cap (research.md R8) keeps each invocation well inside the shared `maxDuration: 30` budget the same way the Misconception Classifier's `MAX_PAIRS_PER_RUN` already does

**Constraints**: Hard-delete only, never anonymize-and-retain (spec 009's locked decision); the cascade must leave zero dangling references and zero denormalized leftovers (FR-004); a demo account (`is_demo = true`) must never be reachable through this pathway (FR-007)

**Scale/Scope**: All three real account types (learner, guardian, instructor) and every existing table that FK's to one, per `data-model.md`'s cascade-order tables -- this is a full first implementation, not an opt-in/per-subject slice

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization Is a Model, Not a Guess | Not implicated -- this feature deletes data, it does not change how mastery is computed | N/A |
| II. Generated Content Is Graded Against a Rubric, Never Vibes | Not implicated -- no new content or grading path | N/A |
| III. One Engine, Many Subjects | Deletion cascade order is keyed entirely on `target_type` (learner/guardian/instructor) and existing FK relationships, never on `subject_id`; zero subject-conditional code (FR-001-FR-010) | PASS |
| IV. Multi-Agent Boundaries Reflect Real Responsibility | No new agent -- this is a data-lifecycle service, not a personalization/grading/tutoring decision. Correctly *not* built as a sixth agent boundary (same reasoning `roadmap.md` already applies to the Quiz feature's in-quiz logic) | PASS |
| V. Every Decision Is Logged and Explainable | `DeletionRequest` itself is the durable, indefinitely-retained audit record of every deletion (who requested it, when, when it completed) -- explicit application-level cascade (research.md R2) exists specifically so this stays true, since a DB-level `ON DELETE CASCADE` would leave no such trail | PASS |
| VI. Agent Boundaries Match Deployment Boundaries | No A2A service touched | N/A |
| VII. Spec Before Code | This plan follows an approved `spec.md`; no `/speckit-clarify` was needed (spec 009 already settled the policy this milestone implements) | PASS |
| VIII. No Real Learner Data Until Privacy/Retention Specified | This *is* the milestone that closes the standing Principle VIII gap (roadmap.md's former "Known gap" entry) -- FR-007's demo-account guard (checked at both submission and execution, research.md R7) ensures this pathway never touches synthetic seed data under the real-account SLA | PASS |
| IX. Deployable and Demoable From the Start | One new Vercel Cron entry in the existing `backend` Service, same shared `maxDuration: 30`; no new Service, no new deployment target | PASS |
| X. Staged Release Discipline | PR into `staging` per usual workflow; no direct-to-`main` path introduced | PASS |

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/020-deletion-pathway/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── api.md            # Phase 1 output -- extends specs/010-instructor-classroom/contracts/api.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── deletion.py             # NEW: POST/GET /api/deletion-requests
│   │   │   └── cron.py                 # + GET /api/cron/execute-deletions
│   │   └── errors.py                   # + DeletionAlreadyPendingError (409, carries deletion_request_id);
│   │                                    #   403/404 cases reuse existing ForbiddenError/NotFoundError
│   └── services/
│       └── deletion/                   # NEW package
│           ├── execute.py              # cascade delete per target_type, data-model.md's ordered tables
│           ├── inactivity.py           # RetentionRecord sweep -> DeletionRequest creation (FR-005)
│           └── authorization.py        # "who may target what" rules from contracts/api.md
└── tests/
    ├── contract/
    │   └── test_deletion_requests_api.py
    ├── integration/
    │   ├── test_deletion_cascade_learner.py
    │   ├── test_deletion_cascade_guardian.py
    │   ├── test_deletion_cascade_instructor.py
    │   ├── test_deletion_inactivity_sweep.py
    │   └── test_deletion_demo_account_guard.py
    └── unit/
        └── test_deletion_authorization.py

vercel.json                              # + one entry in `crons`: /api/cron/execute-deletions
```

**Structure Decision**: Existing `backend` FastAPI Service only --
mirrors the Misconception Classifier's shape exactly (one new routes
module + one new services package + one new cron registration, zero
new Services, zero frontend changes required for the DoD).
