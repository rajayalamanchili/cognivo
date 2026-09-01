# Implementation Plan: Prompt Versioning and Regression Testing

**Branch**: `022-prompt-versioning` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-prompt-versioning/spec.md`

## Summary

Every LLM prompt in `backend/src`, `grading-agent/src`, and `tutor-agent/src` becomes a discoverable, versioned code artifact (a module-level constant/builder paired with a `*_VERSION` string constant, extending the existing `GRADING_LOGIC_VERSION`/`classifier_version` pattern) instead of a bare inline string. A new static-analysis CI check (mirroring `check_no_subject_conditionals.py`'s shape) fails any PR that introduces an unversioned prompt or bumps a prompt's content without bumping its version. Two existing local-only eval scripts (`check_no_subject_conditionals.py`'s sibling for this feature, and `check_grading_agent_eval.py`'s Assessment-Generation counterpart) get wired into CI as blocking gates that re-run automatically when a versioned prompt they cover changes. `GeneratedQuestion` gains a `generation_prompt_version` column, mirroring `grading_logic_version`/`classifier_version`.

## Technical Context

**Language/Version**: Python 3.12 (matches `backend/`, `grading-agent/`, `tutor-agent/`'s existing `uv`-managed environments; no new language)

**Primary Dependencies**: None new. Reuses stdlib `ast` + `subprocess`/`git` (same shape as `check_no_subject_conditionals.py`), the existing `google-adk`/`LiteLlm` call sites, and the existing `alembic`/SQLAlchemy stack for the one new column.

**Storage**: Prompt content + version identifier stay Python code constants (git as the audit trail), not a database row or third-party prompt-management tool -- resolves `tech-stack.md`'s "Prompt-versioning storage mechanism... Milestone 12 decision" (research.md §1). The one new piece of *runtime* storage is a `generation_prompt_version` column on the existing `generated_questions` Postgres table (Neon), added via a normal Alembic migration.

**Testing**: `pytest` (existing, all three service trees already use it). The new scanner and version-bump checks get their own unit tests under `backend/tests/unit/evaluation/`, mirroring `test_no_subject_conditionals.py`.

**Target Platform**: GitHub Actions (`ubuntu-24.04`, existing `backend-tests.yml`/`grading-agent-tests.yml`/`tutor-agent-tests.yml` runners) for the new CI gates; Vercel serverless (existing) for the runtime column read/write -- no change to the deployed execution model itself.

**Project Type**: Existing multi-service monorepo (`backend/` + `grading-agent/` + `tutor-agent/` + `frontend/`) -- this feature adds no new service or project, only files within the three existing engine-source trees plus `.github/workflows/`.

**Performance Goals**: N/A (a CI-time static check and a one-off migration, not a runtime request path). The regression-gate eval runs (FR-005/FR-006) inherit their host workflow's existing job-duration profile -- no new latency budget.

**Constraints**: Must not alter any prompt's instructional content as a side effect of migrating it into a versioned artifact (FR-011/SC-005). The scanner must produce zero false positives against the current, already-migrated codebase (its own acceptance test, FR-003 Acceptance Scenario 1). Fail-closed, not skip, when an eval can't run (mirrors `check_grading_agent_eval.py`'s existing behavior).

**Scale/Scope**: A fixed, small, enumerable set of prompts across three source trees (research.md §2 inventories all of them) -- not an open-ended or growing surface within this milestone.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | Sequencing/Diagnostic/Recommendation have no LLM prompt (research.md §2, confirmed by grep) -- untouched by this feature | PASS |
| II. Generated content graded against a rubric | Grading Agent's rubric-matching logic is unchanged; only its prompt's storage form changes, content byte-identical (FR-011) | PASS |
| III. One engine, many subjects | No subject-conditional logic introduced; the new scanner (research.md §3) is itself subject-agnostic, applying uniformly across all three engine-source trees | PASS |
| IV. Agent boundaries reflect real responsibility | No agent added, removed, or merged. The regression-gate scoping (Assessment-Gen + Grading only) matches which agents already have an independent, real eval suite -- not an arbitrary split | PASS |
| V. Every decision logged and explainable | This feature directly extends this guarantee (FR-009/US3) to the one prompt-driven decision that lacked a version field | PASS (reinforces) |
| VI. Agent boundaries match deployment boundaries | No new A2A service introduced; existing Grading/Tutor A2A boundaries and their inbound-auth requirements are untouched | PASS |
| VII. Spec before code | `spec.md` approved via `/speckit-clarify` (2026-09-01, zero open questions) before this `plan.md` | PASS |
| VIII. No real learner data until privacy specified | No learner data model touched; `GeneratedQuestion` is generated-content metadata, not learner data | PASS |
| IX. Deployable and demoable from the start | New CI checks run in GitHub Actions, not at request time; the one runtime change (a new nullable column, always set to a real value on the new-row write path) requires no in-memory state and fits the existing stateless request path | PASS |
| X. Staged release discipline | Implemented via a normal feature-branch PR into `staging`; strengthens the CI gate rather than bypassing it | PASS |

No violations. Complexity Tracking not needed.

## Project Structure

### Documentation (this feature)

```text
specs/014-prompt-versioning/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── checklists/
│   └── requirements.md  # Already produced by /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature introduces no new or changed
HTTP API surface (research.md §9) -- its only interfaces are CI scripts
and one internal DB column, both fully specified by `research.md` and
`data-model.md`.

### Source Code (repository root)

Existing multi-service monorepo, unchanged in shape. This feature only
adds/edits files within the three existing engine-source trees plus
their CI workflows and one migration:

```text
backend/
├── src/
│   ├── agents/assessment_gen/agent.py      # add GENERATION_PROMPT_VERSION
│   ├── services/grading_client/moderation.py  # add MODERATION_INSTRUCTION_VERSION
│   ├── services/misconception/baseline.py  # add MISCONCEPTION_BASELINE_PROMPT_VERSION
│   ├── models/generated_question.py        # new generation_prompt_version column
│   └── api/routes/{questions,placement}.py # pass the new column at construction
├── scripts/
│   ├── check_prompt_versioning.py          # NEW: FR-003/FR-008 scanner
│   └── batch_eval_questions.py             # add --fresh mode (FR-005)
├── alembic/versions/                       # NEW: alembic revision for the column
└── tests/unit/evaluation/
    ├── test_prompt_versioning.py           # NEW: unversioned-prompt scanner unit tests
    └── test_prompt_version_bump.py         # NEW: version-bump enforcement unit tests

grading-agent/
└── src/
    ├── agent.py                # GRADING_LOGIC_VERSION unchanged (already compliant)
    └── guardrails.py            # add GRADING_GUARDRAIL_MODERATION_VERSION

tutor-agent/
└── src/
    ├── agent.py                 # add TUTOR_INSTRUCTION_VERSION
    └── guardrails.py             # add TUTOR_GUARDRAIL_MODERATION_VERSION

.github/workflows/
├── backend-tests.yml         # + check_prompt_versioning.py step, + batch_eval_questions.py --fresh step
├── grading-agent-tests.yml   # + check_prompt_versioning.py step (eval gate already wired, research.md §6)
└── tutor-agent-tests.yml     # + check_prompt_versioning.py step
```

**Structure Decision**: No new project or service. Every change lands
inside one of the three existing engine-source trees
(`backend/src`, `grading-agent/src`, `tutor-agent/src`), their existing
`scripts/`/`tests/` directories, and their existing per-tree GitHub
Actions workflows -- consistent with this being an engineering-process
capability layered on an already-complete multi-service architecture,
not a new architectural component.
