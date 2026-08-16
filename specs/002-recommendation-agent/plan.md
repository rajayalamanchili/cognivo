# Implementation Plan: Recommendation Agent -- Weak-Area Flagging and Next-Step Suggestions

**Branch**: `002-recommendation-agent` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-recommendation-agent/spec.md`

## Summary

The Recommendation Agent analyzes a learner's existing `MasteryState` and
`AssessmentEvent` rows (Milestone 1's data model -- no new source-of-truth
state) and synthesizes an on-demand weak-area report: which topics are
flagged weak (cited to specific assessment events), which are "not yet
assessed," which have "insufficient data," whether the report should
read as "broad review needed" instead of a top-N list, and a
prerequisite-aware next-step suggestion per flagged topic. Per this
feature's Clarifications, every one of these decisions is deterministic
code reading the mastery model's existing output -- never an LLM's
freeform judgment -- so the agent is a plain Python module (no `LlmAgent`/
`LiteLlm` call), mirroring the Sequencing Agent's `select_next_topic`
precedent rather than the Assessment-Generation Agent's LLM-backed one.
The report is computed fresh on every request (no persisted report
table); each flag and suggestion is written to the existing
`AssessmentEvent` audit log via three new event types, and the whole
request is wrapped in the existing `traced_request()` Langfuse span.

## Technical Context

**Language/Version**: Python 3.12 (matches `backend/pyproject.toml`)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, google-adk (agent
module registration only -- no `LlmAgent`/`LiteLlm` call in this
feature), Pydantic 2 -- all already locked in `tech-stack.md` and
present in `backend/pyproject.toml`; no new dependency needed.

**Storage**: PostgreSQL via Neon (existing schema) -- reads
`MasteryState`, `AssessmentEvent`, `GeneratedQuestion`, `Topic`,
`PrerequisiteEdge`, `Subject`; writes only new `AssessmentEvent` rows
(three new `AssessmentEventType` enum members via an Alembic migration
adding Postgres enum labels). No new table.

**Testing**: `pytest`, following `backend/tests/{unit,integration}/`
per Milestone 1's layout. New scripted mastery-state/assessment-event
scenarios live in a Recommendation-Agent-only module, never imported by
Sequencing's tests (FR-009/SC-005 -- see Constitution Check below).

**Target Platform**: Same deployed Vercel Python Function (FastAPI ASGI
app) as Milestone 1 -- one new router mounted on the existing `app`, no
new deployment unit.

**Project Type**: Web service (existing `backend/` + `frontend/`
monorepo). No frontend change in this milestone -- consuming this
agent's output in a learner-facing UI is Milestone 4's (Learner
Dashboard) explicit job per `roadmap.md` and `CLAUDE.md`; Milestone 2's
`roadmap.md` Definition of Done contains no UI acceptance scenario.

**Performance Goals**: No SC in spec.md states a latency target. The
computation is a handful of indexed reads over a single learner's rows
(small topic counts per `specs/001-domain-agnostic-core`) plus a
bounded prerequisite-graph walk -- expected well within Vercel's default
Function execution window. Per `tech-stack.md`'s "Explicitly not yet
decided" list, Fluid Compute is revisited only if a real latency problem
appears; nothing here suggests it will.

**Constraints**: Stateless per request (no in-memory report cache
across invocations, per Constitution Principle IX / `tech-stack.md`'s
Vercel section) -- every request recomputes from Postgres.

**Scale/Scope**: Single learner per request (spec.md Assumptions);
same two subjects (`algebra-1`, `biology`) as Milestone 1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | This principle is scoped to the Sequencing Agent's mastery state by name, but the same bar is self-imposed here via spec.md FR-011 (Clarifications): weak-topic selection, data-sufficiency status, broad-review threshold, and prerequisite-gap detection are all deterministic code over the BKT model's existing output. | PASS |
| II. Generated content graded against a rubric | N/A -- this agent doesn't generate assessment questions or grade answers. | N/A |
| III. One engine, many subjects | No subject-id-keyed conditional -- reads `Topic`/`PrerequisiteEdge` rows generically per `subject_id`, exactly like `select_next_topic` already does. Covered by the existing `check_no_subject_conditionals.py` SC-004 scan (tech-stack.md), which runs over all of `backend/src/`. | PASS |
| IV. Agent boundaries reflect real responsibility | Spec.md User Story 4 / FR-009 / FR-010 exist specifically to prove this. Recommendation answers "what's the broader pattern across a learner's whole history" (on-demand, multi-topic); Sequencing answers "what's the single next question" (real-time, one topic). Distinct responsibility, distinct failure mode (a wrong weak-area flag vs. a wrong next-question pick), distinct test suite (below). | PASS |
| V. Logged and explainable | FR-008: every flag and suggestion becomes its own `AssessmentEvent` row (new `RECOMMENDATION_REPORT_GENERATED` / `WEAK_AREA_FLAGGED` / `NEXT_STEP_SUGGESTED` types), and the request is wrapped in `traced_request()` for the Langfuse span, matching every other agent invocation. | PASS |
| VI. A2A justified by concrete need | Spec.md Assumptions: local ADK sub-agent, no concrete independent-versioning/deployment need identified. Matches Sequencing/Diagnostic/Assessment-Generation's existing local-only precedent. | PASS |
| VII. Spec before code | This plan follows an approved, clarified spec.md. | PASS |
| VIII. No real learner data | Reads/writes only `DemoLearnerProfile`-scoped rows, same as Milestone 1. No new learner-data surface introduced. | PASS |
| IX. Deployable and demoable | New router mounts on the already-deployed FastAPI app; no new deployment unit or persistent-process assumption. Vercel-live and curl-able immediately after merge. | PASS |
| X. Staged release discipline | Feature branch `002-recommendation-agent` → PR into `staging`, per existing workflow. | PASS (process, not a design gate) |

**FR-009/SC-005 interpretation (recorded here so `/speckit-analyze` and
`/speckit-tasks` don't re-litigate it)**: `tests/conftest.py`'s
`db_session`, `demo_learner`, `algebra_subject`, `biology_subject`
fixtures are shared **test infrastructure** (DB setup, demo-learner
creation, content-artifact loading) that predates both agents and
contains zero agent-specific scripted scenario data -- reusing them is
not a Sequencing/Recommendation fixture-sharing violation. SC-005's
"zero fixtures or assertions" bar is about **evaluation fixtures**: the
scripted mastery-state/assessment-event scenarios that encode "here is
a learner with known weak topics" or "here is a learner ready for the
next question." Those live in agent-specific modules (Sequencing's
existing `tests/integration/test_next_topic_*.py` inline data;
Recommendation's new `tests/integration/recommendation/scenarios.py`)
that the other agent's tests never import. An automated check enforces
this mechanically (see Testing section in research.md and the
`tech-stack.md` addition below), matching the SC-004 precedent of not
relying on code review alone.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-recommendation-agent/
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
│   │   └── recommendation/
│   │       ├── __init__.py
│   │       └── agent.py           # build_weak_area_report(): orchestrates the
│   │                               # deterministic analysis below into a
│   │                               # WeakAreaReport, mirroring agents/sequencing/agent.py's
│   │                               # role relative to services/mastery/
│   ├── services/
│   │   └── recommendation/
│   │       ├── __init__.py
│   │       ├── weak_area.py       # per-topic classification (weak / in_progress /
│   │       │                      # insufficient_data / not_yet_assessed),
│   │       │                      # broad-review threshold (FR-005)
│   │       └── next_step.py       # prerequisite-chain recursion (FR-007)
│   ├── api/routes/
│   │   └── recommendation.py      # GET /api/learners/{learner_id}/recommendations
│   └── models/
│       └── enums.py               # + 3 new AssessmentEventType members
├── alembic/versions/
│   └── <new>_recommendation_event_types.py
└── tests/
    ├── unit/
    │   ├── test_weak_area_classification.py
    │   └── test_next_step_prerequisite_chain.py
    └── integration/
        └── recommendation/
            ├── __init__.py
            ├── scenarios.py       # scripted mastery-state/assessment-event fixtures,
            │                      # never imported by tests/integration/test_next_topic_*.py
            ├── test_weak_area_report.py
            ├── test_broad_review_threshold.py
            ├── test_insufficient_data.py
            ├── test_next_step_suggestions.py
            └── test_audit_log_completeness.py
```

**Structure Decision**: Extends the existing `backend/` monorepo layout
from Milestone 1 -- no new project, no frontend change. Follows the
established `agents/<name>/agent.py` (orchestration) +
`services/<name>/` (pure, independently unit-testable logic) split
already used by `agents/sequencing/agent.py` + `services/mastery/bkt.py`.

## Post-Design Constitution Check

*Re-checked after Phase 1 (data-model.md, contracts/api.md,
quickstart.md).* Phase 1 introduced three concrete decisions beyond the
Phase 0 Constitution Check above: (1) relaxing `AssessmentEvent.topic_id`
to nullable, (2) three new `AssessmentEventType` enum members via
migration, (3) a new CI check script for SC-005. None revisits a
`tech-stack.md`-locked choice (framework, database, deployment target) --
the nullable-column change and enum-migration are additive, backward-
compatible changes to an already-Postgres-backed table using the
already-locked Alembic-per-branch migration workflow, and the CI check
follows the SC-004 precedent already established in `tech-stack.md`
(now recorded there under Testing & evaluation). All ten principles
re-checked above still PASS; no new gate failure.

## Complexity Tracking

*No Constitution Check violations -- table intentionally omitted.*
