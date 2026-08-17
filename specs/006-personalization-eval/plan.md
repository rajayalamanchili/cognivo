# Implementation Plan: Real Personalization Signal -- Sequencing Evaluation Harness

**Branch**: `006-personalization-eval` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-personalization-eval/spec.md`

## Summary

Build an offline evaluation harness that simulates synthetic learner
populations with known ground-truth mastery, runs three ordering
conditions per learner (the real Sequencing Agent's `select_next_topic`,
a random baseline, and a fixed canonical-order baseline), and measures
questions-to-mastery for each. The harness is a manually-run Python
script (no CI automation, no LLM calls -- research.md §1) that writes a
self-describing JSON Comparison Report; an engineer commits that file to
publish it. A new read-only FastAPI endpoint serves the latest published
report, and a new Next.js page -- linked from main navigation -- renders
it in plain language as part of the live demo (Clarifications).

## Technical Context

**Language/Version**: Python 3.12 (harness + backend route, matching
`backend/pyproject.toml`); TypeScript/Next.js (report page, matching
`frontend/`)

**Primary Dependencies**: None new. Reuses SQLAlchemy/FastAPI/pytest
(backend) and Next.js/React (frontend) already locked in `tech-stack.md`.
No LLM/ADK calls in the harness loop (research.md §1), so no new
Langfuse/ADK wiring either.

**Storage**: PostgreSQL (Neon, existing) -- reuses `DemoLearnerProfile`,
`MasteryState`, and `AssessmentEvent` tables as-is for the Sequencing
Agent condition only (research.md §6-§7); no new tables or migrations.
The published Comparison Report is a committed JSON file
(`backend/evaluation/reports/latest.json`), not a database row
(research.md §8).

**Testing**: `pytest` (harness unit tests: ground-truth generation
determinism, each condition's mechanics, convergence/non-convergence
logic, report-shape validation) + existing `Vitest`/Playwright conventions
for the new frontend route.

**Target Platform**: Same Vercel deployment (Python Function + Next.js)
as every prior milestone; the harness itself is a local/dev-only script,
never invoked from a request (research.md §6, §8).

**Project Type**: Web application (existing `backend/` + `frontend/`
structure) -- no new top-level project.

**Performance Goals**: No request-time computation budget beyond a
normal page load -- the report page only reads a small committed JSON
file (contracts/api.md). The harness itself has no latency target (it's
an offline script); ~720 simulated learner-runs with no LLM calls is
expected to complete in well under a minute locally.

**Constraints**: Harness must never touch real learner data (FR-009);
must call the real `select_next_topic` function, not a reimplementation
(FR-008); must be deterministic given a fixed seed (FR-007); must not
require a CI job or request-time re-run (Clarifications).

**Scale/Scope**: 4 synthetic learner profiles x 2 subjects (Algebra I,
Biology, both 8 topics) x 3 conditions x 30 simulated learners = 720
learner-runs per Evaluation Run, budget-capped at 20 questions/topic
(research.md §10).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Assessment |
|---|---|
| I. Personalization is a model, not a guess | PASS -- the Sequencing Agent condition calls the real, deterministic `select_next_topic` (BKT-driven); no LLM involved in ordering decisions. |
| II. Generated content graded against a rubric | N/A -- the harness generates no real assessment content; simulated correctness uses the already-locked BKT emission parameters, not new grading logic. |
| III. One engine, many subjects | PASS -- harness code is subject-agnostic (`subject_id` parameter only); covered by the existing `check_no_subject_conditionals.py` scan (research.md §11). |
| IV. Agent boundaries reflect real responsibility | PASS -- no new agent or agent boundary introduced; the harness is a caller of the existing Sequencing Agent's tool function, like a test. |
| V. Every decision logged and explainable | PASS -- the Sequencing Agent condition writes real `AssessmentEvent` rows (reusing `NEXT_TOPIC_SELECTED`) for every decision, exactly as production does, cleaned up at run end (research.md §7, revised post-`/speckit-analyze`). Random/fixed-order conditions write none, but they touch no DB row at all and aren't real agent decisions, so there is nothing for this principle to apply to. The Comparison Report is also self-describing (FR-013/FR-014). |
| VI. A2A justified by concrete need | N/A -- no A2A involved. |
| VII. Spec before code | PASS -- this plan follows an approved, clarified `spec.md`. |
| VIII. No real learner data | PASS -- synthetic-only, `is_demo=True` learners (research.md §6), cleaned up after each run; SC-006 gives this an automated check. |
| IX. Deployable and demoable | PASS -- the report page ships as part of this milestone's live deployment (Clarifications: Option C), reachable without auth from main navigation. |
| X. Staged release discipline | PASS -- standard branch/PR workflow, no exception needed. |

No violations; no Complexity Tracking entries needed.

**Post-Phase-1 re-check**: Table above already reflects Phase 0/1
findings (research.md, data-model.md) -- no new violation surfaced by
the detailed design (e.g. the FK-driven decision to persist only the
Sequencing Agent condition's synthetic learners, research.md §6, doesn't
touch real learner data or introduce a new agent boundary). Gate remains
PASS.

**Revision note** (post-`/speckit-analyze`): An earlier version of this
plan proposed skipping `AssessmentEvent` audit-log writes for the
Sequencing Agent condition, justified via a Principle-V scope narrowing
that `/speckit-analyze` correctly flagged as an unauthorized
reinterpretation of a MUST clause (finding C1). Resolved by full
compliance instead (research.md §7) -- the Complexity Tracking table
that previously justified the deviation is removed below, since there is
no longer a violation to justify.

## Project Structure

### Documentation (this feature)

```text
specs/006-personalization-eval/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── services/
│   │   └── evaluation/
│   │       ├── __init__.py
│   │       ├── profiles.py       # SyntheticLearnerProfile definitions + ground-truth generation (research.md §3, §10)
│   │       ├── conditions.py     # sequencing/random/fixed_order condition loops (research.md §1, §4, §6)
│   │       ├── report.py         # ComparisonReport aggregation + JSON (de)serialization (data-model.md)
│   │       └── run_harness.py    # CLI entry point (`python -m src.services.evaluation.run_harness`)
│   └── api/
│       └── routes/
│           └── evaluation.py     # GET /api/evaluation/report (contracts/api.md)
├── evaluation/
│   └── reports/
│       └── latest.json           # Published Comparison Report (committed manually, research.md §8)
└── tests/
    ├── unit/
    │   └── evaluation/
    │       ├── test_ground_truth_determinism.py
    │       ├── test_condition_mechanics.py
    │       └── test_report_shape.py
    └── integration/
        └── evaluation/
            └── test_sequencing_condition_real_code_path.py  # FR-008/SC-004: asserts select_next_topic is called, not reimplemented

frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx                    # add minimal main-nav (research.md §9)
│   │   └── personalization-eval/
│   │       ├── page.tsx
│   │       └── personalization-eval-report.tsx
│   └── services/
│       └── api.ts                        # add getEvaluationReport()
└── tests/
    └── e2e/
        └── personalization-eval-report.spec.ts  # Playwright, SC-005
```

**Structure Decision**: Extends the existing `backend/src/services/*` +
`backend/src/api/routes/*` + `frontend/src/app/*` pattern already used by
every prior milestone (e.g. `services/recommendation/` +
`api/routes/recommendation.py` + a dedicated frontend route). No new
top-level directories beyond `backend/evaluation/reports/` for the
published artifact itself, which is data, not code.

## Complexity Tracking

*No entries -- Constitution Check has no unresolved violations (see Revision note above).*
