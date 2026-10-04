# Implementation Plan: Full K-12 Content Catalog

**Branch**: `040-k12-content-catalog` | **Date**: 2026-10-04 | **Spec**: `specs/040-k12-content-catalog/spec.md`

**Input**: Feature specification from `specs/040-k12-content-catalog/spec.md`

## Summary

Author two new subject content artifacts — Algebra II and Physics — using
the exact schema Algebra I and Biology already use (topics, prerequisites,
skill definitions, difficulty calibration, Milestone 038 standards tags,
Milestone 039 career connections). Each is drafted with LLM assistance and
reviewed/approved via a normal PR before being loaded with the existing
`scripts/load_content_artifact.py`, exercising zero new or changed engine
code. This is a deliberate two-subject pilot proving the "zero engine
change" claim and the authoring approach at small scale before the
remaining six named subjects (Pre-Algebra, Geometry, Chemistry, Earth
Science, Elementary Math, Elementary Science) are attempted in a follow-up
feature.

## Technical Context

**Language/Version**: Python 3.12 (backend, FastAPI), TypeScript 5 (frontend, Next.js/React) — already locked in `tech-stack.md`, no change.

**Primary Dependencies**: None new (ladder step 5). Reuses `src/services/content_artifact/loader.py` and `validator.py` unchanged, `scripts/load_content_artifact.py` unchanged, the existing subject-picker/placement/practice/quiz-assignment frontend components unchanged.

**Storage**: PostgreSQL via Neon. **Zero schema changes** — this feature writes only new rows (two `Subject` rows, their `Topic` rows, `GradeBand` rows for grades 9-11, `StandardsTag` and `career_connection`-bearing `Topic` rows) into tables that already exist from Milestones 1/15/038/039. No migration.

**Testing**: `pytest` (backend contract/unit/integration), `Vitest` + React Testing Library (frontend) — existing patterns, no new tooling. New test fixtures: two content-artifact files loaded against the existing validator test suite, plus the existing acceptance-scenario suites (placement, practice, quiz assignment, instructor dashboard) parametrized or re-run against the two new `subject_id`s to prove SC-003/SC-004.

**Target Platform**: Vercel serverless (existing). Content-artifact loading is a one-time, maintainer-run script invocation against each environment's database (same manual step every prior content addition has used, including Milestone 10's documented deploy-hook gotcha) — not a runtime process.

**Project Type**: Web application (existing `backend/` + `frontend/` split). No new frontend component: both new subjects appear automatically in the existing subject-picker, placement, practice, and instructor-assignment UI the moment their content artifact is loaded, since none of those components branch on `subject_id` (Constitution Principle III).

**Constraints**: Must introduce zero subject-id-keyed conditional anywhere in engine source, verified by the existing `scripts/check_no_subject_conditionals.py` continuing to pass unmodified (FR-007). Content MUST be authored as an LLM-assisted draft with mandatory human review via a normal reviewed PR before merge/load (FR-004) — no new review-queue UI or workflow state. `Topic.prerequisites` entries are validated by the existing loader to resolve only within the same subject (`validator.py`'s `prereqs_by_topic` check) — cross-subject prerequisites (e.g. Algebra II depending on Algebra I) are not an engine capability and are out of scope; any such dependency is a content-authoring note only (research.md Decision 2), never an enforced prerequisite edge.

**Scale/Scope**: Two new `subject.yaml` content artifacts, each with a topic count comparable to Algebra I's existing 16 topics (research.md Decision 1 records the actual authored topic lists). Algebra II declares `grade_bands: [9, 10]`; Physics declares `grade_bands: [9, 10, 11]` (Clarifications, 2026-10-04) — real-world-accurate secondary bands, independent of Algebra I's own compressed 6-8 banding. Every topic in both subjects carries a standards tag and career connection (FR-002); whichever topics the authoring pass designates as free-text-capable flow through the existing Grading Agent/rubric/misconception-classification path with no special-casing (FR-007/FR-008).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization is a model, not a guess | The Sequencing Agent's deterministic BKT model is reused unchanged per subject — Algebra II/Physics mastery state is computed by the exact same tool call as every existing subject's. No new or subject-specific mastery logic. | PASS |
| II. Rubric-graded, never vibes | Every free-text-capable topic in the new subjects gets a rubric generated alongside its question via the existing Assessment-Generation/Grading Agent mechanism — content authoring supplies the topic's `skill_definition`/`difficulty_calibration`, not a rubric itself (rubrics are generated per-question, same as today). No change to how a rubric is produced. | PASS |
| III. One engine, many subjects | This feature is itself a direct test of this principle: two more subjects, zero new subject-conditional code, `check_no_subject_conditionals.py` must stay green (FR-007, SC-005). | PASS — primary gate for this feature |
| IV. Agent boundaries reflect real responsibility | No new agent, no new A2A service — pure content-artifact volume addition over existing routes/agents. | N/A |
| V. Logged and explainable | Every placement/practice/quiz/grading/mastery-update event for the new subjects flows through the existing audit-log and Langfuse tracing mechanisms automatically, since no new code path is introduced. No new event type needed. | PASS |
| VI. A2A boundary discipline | N/A — no A2A service touched. | N/A |
| VII. Spec before code | This plan follows an approved, clarified `spec.md` (one clarification session, grade bands resolved, zero outstanding markers). | PASS |
| VIII. No real data until privacy is specified | No new learner-identifying data — content artifacts carry no PII. New-subject validation uses the existing seeded demo learner, matching every prior content-addition milestone's precedent (Milestone 1 User Story 3, Milestone 10). | PASS |
| IX. Deployable/stateless | Content-artifact loading is the existing one-time maintainer-run script against each environment's DB — no new background process, no new runtime state. Milestone 10's documented deploy-hook gotcha (a schema migration sometimes needing manual re-trigger) is noted as a watch-item for this feature's rollout, though this feature itself adds no migration. | PASS |
| X. Staged release discipline | Standard feature-branch → `staging` PR → `main` promotion, same as every prior milestone. Content load against each environment's DB is a manual post-merge step, same as Milestones 1/10/038/039. | PASS |

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/040-k12-content-catalog/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command) -- empty, see note below
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── content/
│   ├── algebra-1/            # existing, unchanged
│   ├── biology/               # existing, unchanged
│   ├── algebra-2/             # NEW: subject.yaml (+ images/ only if a topic needs one)
│   └── physics/                # NEW: subject.yaml (+ images/ only if a topic needs one)
├── src/
│   ├── services/content_artifact/   # existing loader.py / validator.py -- UNCHANGED
│   └── ...                           # every other engine module -- UNCHANGED
└── tests/
    ├── unit/                 # existing content-artifact validator tests re-run against new fixtures
    └── integration/          # existing placement/practice/quiz-assignment suites re-run/parametrized against algebra-2, physics

frontend/
└── src/                       # UNCHANGED -- subject picker, placement, practice, instructor-assignment
                                 # UI already render generically off loaded Subject rows
```

**Structure Decision**: Existing web-application structure (`backend/` + `frontend/`) is unchanged. The only new filesystem additions are two content directories under `backend/content/`; no new `src/` module, no new frontend component, no new migration. This mirrors Milestone 1 User Story 2's original "second subject proves the engine" pattern exactly, just with two more subjects.

**Contracts note**: No new or changed API contract. Every endpoint this feature touches (subject listing, placement start, practice start, quiz-assignment creation, instructor dashboard) already accepts an arbitrary loaded `subject_id` with no enumerated allow-list — confirmed by reading `src/services/content_artifact/loader.py` and the relevant route handlers, which select on whatever `Subject` rows exist in the database. `contracts/` is therefore intentionally left without a new contract file; `research.md` Decision 4 records this finding.

## Complexity Tracking

*No violations — table omitted.*
