# Implementation Plan: STEM Catalog Expansion (Remaining Six Subjects)

**Branch**: `046-stem-catalog-expansion` | **Date**: 2026-10-12 | **Spec**: `specs/046-stem-catalog-expansion/spec.md`

**Input**: Feature specification from `specs/046-stem-catalog-expansion/spec.md`

## Summary

Author six new subject content artifacts -- Pre-Algebra, Geometry,
Chemistry, Earth Science, Elementary Math, and Elementary Science --
using the exact schema the four already-loaded subjects (Algebra I,
Biology, Algebra II, Physics) use (topics, prerequisites, skill
definitions, difficulty calibration, Milestone 038 standards tags,
Milestone 039 career connections). Each is drafted with LLM assistance
and reviewed/approved via a normal PR before being loaded with the
existing `scripts/load_content_artifact.py`. Unlike Milestone 040's
pilot, this feature needs **zero engine changes**: roster-grade
validation (`GradeBand`, `_check_grade_matches_subject`) already
supports the full `grade BETWEEN 1 AND 12` range (`ck_grade_bands_grade_range`
check constraint), and Milestone 19's mediation-tier logic
(`determine_mediation_tier`) already maps grades 1-2 and 3-5 to real
tiers (`CO_PRESENT`, `CHECK_IN`) -- so Elementary Math/Science (the
first subjects below grade 6) require no new adaptive-UI code path.
This closes the "Full K-12 STEM content catalog" roadmap backlog item.

## Technical Context

**Language/Version**: Python 3.12 (backend, FastAPI), TypeScript 5 (frontend, Next.js/React) -- already locked in `tech-stack.md`, no change.

**Primary Dependencies**: None new (ladder step 5). Reuses `src/services/content_artifact/loader.py` and `validator.py` unchanged, `scripts/load_content_artifact.py` unchanged, the existing subject-picker/placement/practice/quiz-assignment frontend components unchanged.

**Storage**: PostgreSQL via Neon. New rows only, zero schema change -- six `Subject` rows, their `Topic` rows, `GradeBand` rows (including, for the first time, grades 1-5 for the two elementary subjects -- already a legal range per `ck_grade_bands_grade_range`), `StandardsTag` and career-connection-bearing `Topic` rows into tables that already exist from Milestones 1/15/038/039/040. No migration needed.

**Testing**: `pytest` (backend contract/unit/integration), `Vitest` + React Testing Library (frontend) -- existing patterns, no new tooling. New fixtures per subject (mirroring the existing `algebra_subject`/`biology_subject`/`algebra_2_subject`/`physics_subject` pattern) plus dedicated integration test files exercising placement/practice, grade-filtering (reusing Milestone 040's FR-009 check against each new `grade_bands`), cold-start-degradation, and quiz-assignment flows against all six new `subject_id`s -- including Elementary Math/Science's first real exercise of grades 1-5 against `determine_mediation_tier`'s `CO_PRESENT`/`CHECK_IN` branches.

**Target Platform**: Vercel serverless (existing). Content-artifact loading is a one-time, maintainer-run script invocation against each environment's database, same manual step every prior content addition has used.

**Project Type**: Web application (existing `backend/` + `frontend/` split). No new frontend component: all six new subjects appear automatically in the existing subject-picker, placement, practice, and instructor-assignment UI the moment their content artifact is loaded, since none of those components branch on `subject_id` (Constitution Principle III).

**Constraints**: Must introduce zero subject-id-keyed conditional anywhere in engine source, verified by the existing `scripts/check_no_subject_conditionals.py` continuing to pass unmodified (FR-007). `Topic.prerequisites` entries are validated by the existing loader to resolve only within the same subject -- cross-subject prerequisites (e.g. Geometry depending on Pre-Algebra) are not an engine capability and are out of scope; any such dependency is a content-authoring note only, never an enforced prerequisite edge (same precedent Milestone 040 set for Algebra II/Algebra I).

**Scale/Scope**: Six new `subject.yaml` content artifacts. Proposed `grade_bands` (confirmed during authoring, not locked by this plan): Elementary Math `[1,2,3,4,5]`, Elementary Science `[1,2,3,4,5]`, Pre-Algebra `[6,7]`, Geometry `[9,10]`, Chemistry `[9,10]`, Earth Science `[6]`. Every topic in every new subject carries a standards tag and career connection (FR-002); whichever topics authoring designates as free-text-capable flow through the existing Grading Agent/rubric/misconception-classification path with no special-casing (FR-007/FR-008).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Personalization is a model, not a guess | The Sequencing Agent's deterministic BKT model is reused unchanged per subject -- each new subject's mastery state is computed by the exact same tool call as every existing subject's. No new or subject-specific mastery logic. | PASS |
| II. Rubric-graded, never vibes | Every free-text-capable topic in the six new subjects gets a rubric generated alongside its question via the existing Assessment-Generation/Grading Agent mechanism. No change to how a rubric is produced. | PASS |
| III. One engine, many subjects | Primary gate for this feature: six more subjects, zero new subject-conditional code, `check_no_subject_conditionals.py` must stay green (FR-007, SC-005). | PASS |
| IV. Agent boundaries reflect real responsibility | No new agent, no new A2A service -- pure content-artifact volume addition over existing routes/agents. | N/A |
| V. Logged and explainable | Every placement/practice/quiz/grading/mastery-update event for the new subjects flows through the existing audit-log and Langfuse tracing mechanisms automatically, since no new code path is introduced. | PASS |
| VI. A2A boundary discipline | N/A -- no A2A service touched. | N/A |
| VII. Spec before code | This plan follows an approved `spec.md` with zero outstanding `[NEEDS CLARIFICATION]` markers (scope resolved by the project's own prior roadmap decision). | PASS |
| VIII. No real data until privacy is specified | No new learner-identifying data -- content artifacts carry no PII. New-subject validation uses the existing seeded demo learner, matching every prior content-addition milestone's precedent. | PASS |
| IX. Deployable/stateless | Content-artifact loading is the existing one-time maintainer-run script against each environment's DB -- no new background process, no new runtime state, no migration. | PASS |
| X. Staged release discipline | Standard feature-branch -> `staging` PR -> `main` promotion, same as every prior milestone. Content load against each environment's DB is a manual post-merge step. | PASS |

No violations. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/046-stem-catalog-expansion/
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
│   ├── algebra-2/             # existing, unchanged
│   ├── physics/                # existing, unchanged
│   ├── pre-algebra/            # NEW: subject.yaml (+ images/ only if a topic needs one)
│   ├── geometry/                # NEW: subject.yaml
│   ├── chemistry/                # NEW: subject.yaml
│   ├── earth-science/             # NEW: subject.yaml
│   ├── elementary-math/            # NEW: subject.yaml
│   └── elementary-science/          # NEW: subject.yaml
├── src/
│   ├── services/content_artifact/   # existing loader.py / validator.py -- UNCHANGED
│   ├── services/roster/enrollment.py # existing FR-009 grade check (Milestone 040) -- UNCHANGED
│   └── ...                           # every other engine module -- UNCHANGED
└── tests/
    ├── unit/                 # existing content-artifact validator tests re-run against new fixtures
    └── integration/          # new dedicated test files (placement/practice, grade-filtering, cold-start, quiz-assignment) against each of the six new subject_ids

frontend/
└── src/                       # UNCHANGED -- subject picker, placement, practice, instructor-assignment
                                 # UI already render generically off loaded Subject rows
```

**Structure Decision**: Existing web-application structure (`backend/` + `frontend/`) is unchanged. The only new filesystem additions are six content directories under `backend/content/`; no new frontend component, no new `src/` module, no migration -- a strict subset of Milestone 040's structure (that pilot needed one new engine column for FR-009; this feature reuses that unchanged).

**Contracts note**: No API contract changes. Every placement/practice/quiz-assignment/instructor-dashboard/roster endpoint already accepts an arbitrary loaded `subject_id` with no enumerated allow-list (confirmed by reading `src/services/content_artifact/loader.py` and the relevant route handlers), and `POST /api/rosters`'s `grade` field already exists from Milestone 040. `contracts/README.md` records this explicitly rather than an empty directory.

## Complexity Tracking

*No violations -- table omitted.*
