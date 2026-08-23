# Implementation Plan: Instructor Classroom -- Auth, Rosters, Dashboard, Content Review

**Branch**: `010-instructor-classroom` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-instructor-classroom/spec.md`

## Summary

Introduces this project's first real (non-demo, non-synthetic)
accounts, built directly against `specs/009-privacy-retention`'s
already-approved policy and forward-looking data model. A guardian and
an instructor each get their own account type with independently-unique
email (research.md §2); a guardian adds learner profiles and enrolls
them into an instructor's subject-scoped roster (open: self-serve via
join code; closed: instructor-approved); an instructor's dashboard
aggregates each enrolled learner's existing, unmodified Recommendation
Agent output (Milestone 2) -- no new weak-area logic; and an instructor
triages Milestone 1's already-existing flagged-question mechanism
(FR-011) for learners on their own roster(s). Seeded demo instructor
and student accounts extend Milestone 1's existing demo-account pattern
so the live deployment stays demoable without real sign-up.

## Technical Context

**Language/Version**: Python 3.12 backend (unchanged), TypeScript/
Next.js frontend (unchanged) -- no new deployable unit.

**Primary Dependencies**: Backend adds `argon2-cffi` (Argon2id password
hashing) and `pyjwt` (session token issuing/verification) --
`tech-stack.md`'s new Authentication section locks both, rejecting a
third-party auth provider (research.md §1). No other new dependencies;
the dashboard reuses `src/agents/recommendation/agent.py`'s existing
`build_weak_area_report` unmodified.

**Storage**: PostgreSQL via Neon, same database as every other
milestone. Eight new tables (`real_guardian_accounts`,
`real_instructor_accounts`, `classroom_rosters`, `enrollments`,
`enrollment_requests`, `deletion_requests`, `retention_records`,
`demo_instructor_profiles`) plus a rename-and-extend of the existing
`demo_learner_profiles` table to `learner_profiles` (adds nullable
`guardian_id`/`retention_record_id` -- data-model.md's Correction to
spec 009's originally-proposed separate table, found incompatible with
5 existing hard FKs). Concretizes spec 009's `data-model.md`, which
deliberately shipped no migration itself (research.md §3 there) since
nothing used the tables yet. One new Alembic migration.

**Testing**: `pytest` (`backend/tests/{unit,integration}/`) for
password hashing/JWT verification, roster enrollment-gating logic
(open/closed, FR-005/FR-006), unenrollment (FR-007a), dashboard
aggregation matching the underlying recommendations endpoint
byte-for-byte (SC-001), cross-tenant isolation (SC-002), content-review
resolution and its audit event (FR-013), and spec 009's
`check_no_real_account_path.py` gate now actually exercised against
these new models (must pass -- every new account-shaped model carries
`is_demo`). `Vitest` + React Testing Library for the new auth forms,
roster management UI, dashboard, and content-review queue components.
`Playwright` (E2E) extended to cover a full sign-up -> roster-create ->
enroll -> dashboard-view round trip against the live dev deployment.

**Target Platform**: The existing `backend/`+`frontend/` Vercel Services
project -- no new deployable unit, unlike Milestone 6's Grading Agent.

**Project Type**: Web application (unchanged two-project structure).

**Performance Goals**: Dashboard for a roster of up to 30 enrolled
learners (a realistic class-size ceiling) loads within 5 seconds.
Achievable without parallel/async fan-out machinery:
`build_weak_area_report` makes no LLM/network call (it's pure
Postgres-query classification, per `recommendation.py`'s own
docstring), so N sequential in-process calls for a 30-learner roster is
bounded by ordinary DB query latency, not external I/O -- confirmed
sufficient in research.md §4 rather than assumed.

**Constraints**: The JWT session cookie MUST be `httpOnly`, `Secure`,
`SameSite=Lax` -- no client-side JavaScript ever reads the token
directly (XSS mitigation). No server-side session store -- verification
must be a pure function of the JWT's signature and claims (Constitution
Principle IX's stateless-serverless constraint, tech-stack.md's
Authentication section).

**Scale/Scope**: 8 new tables, ~9 new API route groups (register x2,
login x2, logout, roster CRUD, enrollment, unenrollment,
dashboard, content-review), new frontend pages (guardian/instructor
sign-up and sign-in, roster management, dashboard, content-review
queue, extended demo entry point).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1
design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | Not implicated -- no mastery-model code touched. | N/A |
| II. Generated content graded against a rubric | Not implicated -- no content generation/grading in this feature. | N/A |
| III. One engine, many subjects | `ClassroomRoster.subject_id` is a DB value read at query time, never a hardcoded literal in engine source -- covered by the existing `check_no_subject_conditionals.py` scan, unaffected by this feature. | PASS |
| IV. Agent boundaries reflect real responsibility | The dashboard is an aggregation layer over Milestone 2's existing `build_weak_area_report`, called once per enrolled learner -- explicitly not a new weak-area classification implementation (spec.md FR-008, SC-001 makes this a measurable, tested guarantee, not just a stated intent). | PASS |
| V. Logged and explainable | Enrollment, unenrollment, and flagged-question resolution are each a distinct, audited event (FR-013, data-model.md) -- "why is this learner on this roster" and "why was this flag resolved this way" both have real, traceable answers, extending Principle V beyond grading/sequencing decisions for the first time. | PASS |
| VI. A2A justified by concrete need | Not implicated -- no new agent or service boundary. | N/A |
| VII. Spec before code | Full lifecycle followed: spec 009 (approved, merged) -> this spec -> `/speckit-clarify` (2 questions resolved) -> this plan. | PASS |
| VIII. No real learner data | This is the milestone where real accounts are first created -- gated on spec 009's approval (met) and its `check_no_real_account_path.py` CI check. `RealGuardianAccount`/`RealInstructorAccount`/`DemoInstructorProfile` all carry non-nullable `is_demo`, satisfying the gate directly; `LearnerProfile` (renamed from `DemoLearnerProfile`) already does too and is unaffected by this feature's column additions. The gate's role here isn't to block these tables outright -- once spec 009's conditions are met (they are), real accounts are the intended, gated-for outcome, not a violation. | PASS (conditions met) |
| IX. Deployable and demoable | JWT-in-cookie auth is stateless by construction (tech-stack.md) -- no persistent session-server assumption. Demo instructor/student accounts (FR-014) keep the live deployment demoable without real sign-up. | PASS |
| X. Staged release discipline | Feature branch `010-instructor-classroom` -> PR into `staging`, same as every prior feature. | PASS |

No violations requiring Complexity Tracking.

**Post-Phase-1 re-check**: Phase 1 design surfaced a real correction to
spec 009's proposed data model (a separate `RealLearnerAccount` table
was incompatible with 5 existing hard FKs to `demo_learner_profiles`;
data-model.md §"Correction" documents the fix -- extend that table in
place, renamed to `learner_profiles`, rather than create a new one).
This changes *where* real-learner data lives, not *whether* Principle
VIII's requirements are met -- `is_demo` remains the non-nullable
discriminator `check_no_real_account_path.py` checks, and
`guardian_id`/`retention_record_id` being nullable-but-required-for-
real-rows is enforced at the application layer the same way this
codebase already enforces comparable invariants. Constitution Check
table above still holds unchanged; no new violation introduced.

## Project Structure

### Documentation (this feature)

```text
specs/010-instructor-classroom/
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
│   │   ├── demo_learner_profile.py      # RENAMED to learner_profile.py --
│   │   │                                  # DemoLearnerProfile -> LearnerProfile,
│   │   │                                  # + guardian_id/retention_record_id
│   │   │                                  # (data-model.md's Correction)
│   │   ├── real_guardian_account.py     # NEW
│   │   ├── real_instructor_account.py   # NEW
│   │   ├── classroom_roster.py          # NEW -- includes subject_id
│   │   ├── enrollment.py                # NEW
│   │   ├── enrollment_request.py        # NEW
│   │   ├── deletion_request.py          # NEW
│   │   ├── retention_record.py          # NEW
│   │   └── demo_instructor_profile.py   # NEW -- LearnerProfile's demo-row
│   │                                       # pattern, extended to instructors
│   ├── services/
│   │   ├── auth/                        # NEW
│   │   │   ├── passwords.py             # Argon2id hash/verify
│   │   │   ├── tokens.py                # JWT issue/verify (tech-stack.md)
│   │   │   └── dependencies.py          # FastAPI Depends() for "current guardian"/
│   │   │                                  # "current instructor" from the session cookie
│   │   ├── roster/                      # NEW
│   │   │   └── enrollment.py            # open/closed join logic (FR-005/FR-006),
│   │   │                                  # unenrollment (FR-007a)
│   │   ├── dashboard/                    # NEW
│   │   │   └── aggregation.py           # fans out to build_weak_area_report
│   │   │                                  # per enrolled learner (FR-008)
│   │   └── content_review/               # NEW
│   │       └── resolution.py            # reactivate/reject a flagged question (FR-012)
│   └── api/routes/
│       ├── auth.py                       # NEW -- register/login/logout
│       ├── rosters.py                    # NEW -- roster CRUD, join, approve/decline,
│       │                                    # unenroll
│       ├── instructor_dashboard.py       # NEW
│       └── content_review.py             # NEW
├── alembic/versions/
│   └── <new>_instructor_classroom.py     # NEW -- 8 new tables
└── scripts/
    └── seed_demo_instructor.py           # NEW -- Milestone 1's seed_demo_learner.py
                                             # pattern, extended to instructors

frontend/
└── src/app/
    ├── (auth)/
    │   ├── guardian/{register,sign-in}/  # NEW
    │   └── instructor/{register,sign-in}/# NEW
    ├── instructor/
    │   ├── rosters/                      # NEW -- create/list, join-request approval
    │   ├── dashboard/                    # NEW
    │   └── review/                       # NEW -- content-review queue
    └── demo/                             # EXTENDED -- adds a demo-instructor entry
                                             # point alongside the existing demo-learner one
```

**Structure Decision**: Extends the existing two-project (`backend/`,
`frontend/`) structure -- no new deployable unit. New backend code is
organized the same way every prior milestone's has been (`models/`,
`services/<concern>/`, `api/routes/`), keeping `services/auth/` fully
separate from `services/grading_client/`, `services/mastery/`, etc.,
since authentication is a cross-cutting concern every route depends on,
not a feature-specific service module.

## Complexity Tracking

No violations -- table not needed.
