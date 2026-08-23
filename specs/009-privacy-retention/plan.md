# Implementation Plan: Privacy & Retention Spec -- the Real Learner Data Gate

**Branch**: `009-privacy-retention` | **Date**: 2026-08-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-privacy-retention/spec.md`

## Summary

Delivers the Constitution Principle VIII gate itself: a written data
classification (FR-002) covering every field a real learner/instructor
account would carry, its retention period, and its deletion trigger;
and an automated, CI-enforced gate script that fails if any code path
in `backend/src` can create or persist a real (non-`is_demo`) account
before this spec's other requirements (deletion, access control, demo
distinguishability) are satisfiable. This spec does not build Milestone
7 proper's actual account/roster/dashboard features -- no new database
tables, no new API routes, no UI. Its concrete forward-looking data
model (`RealGuardianAccount`, `RealLearnerAccount`, `RealInstructorAccount`,
`ClassroomRoster`, `DeletionRequest`, `RetentionRecord`) exists in
`data-model.md` as the shape Milestone 7 proper's own plan must
implement against, not as tables this plan creates.

## Technical Context

**Language/Version**: Python 3.12, matching `backend/scripts/`'s
existing convention (`check_no_subject_conditionals.py`) -- this
feature's only code deliverable is a script of the same kind.

**Primary Dependencies**: None new. The gate script (FR-001/FR-008)
uses only the Python standard library (`ast` for parsing SQLAlchemy
model definitions -- see research.md §1), same as
`check_no_subject_conditionals.py`'s plain-`re`-over-source approach.

**Storage**: No new tables and no migration in this spec. The six
entities in `data-model.md` are a forward-looking schema for Milestone
7 proper's own plan to implement, not persisted by this feature.

**Testing**: `pytest` (`backend/tests/unit/test_check_no_real_account_path.py`)
-- verifies the gate script passes against the current codebase and
fails against a synthetic fixture introducing an account-shaped model
without `is_demo`.

**Target Platform**: Runs inside the existing `backend-tests.yml`
GitHub Actions workflow's `pytest` step, via a pytest test that imports
the gate function directly -- the same pattern already used for
`check_no_subject_conditionals.py` (research.md §2, corrected during
implementation from an earlier, inaccurate claim that no such CI wiring
existed). No workflow file changes, no live Postgres or API key needed.

**Project Type**: Documentation + a CI gate script -- no user-facing
feature, no new deployable unit.

**Performance Goals**: N/A -- a CI-time static check, not a runtime
request path.

**Constraints**: The gate script MUST run without a live database
connection or `ANTHROPIC_API_KEY`, so it stays cheap enough to run on
every PR (unlike this project's DB-requiring integration suites).

**Scale/Scope**: One gate script, one new CI step, one written data-
classification document (`data-classification.md`). No application
code changes -- no real accounts are created by this spec.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1
design below.*

| Principle | Check | Status |
|---|---|---|
| I. Personalization is a model, not a guess | Not implicated -- this spec touches no mastery-model code. | N/A |
| II. Generated content graded against a rubric | Not implicated -- no content generation or grading in this spec. | N/A |
| III. One engine, many subjects | The gate script contains no subject-id-keyed logic; it inspects model/table shape only. Covered by the existing `check_no_subject_conditionals.py` scan, which this spec doesn't touch. | PASS |
| IV. Agent boundaries reflect real responsibility | Not implicated -- no agents involved. | N/A |
| V. Logged and explainable | `DeletionRequest` (data-model.md) is itself an audit record -- submission time, completion time, target identity -- proof the FR-004 SLA was met. `RetentionRecord` gives every future real account a traceable "who authorized this enrollment" answer (FR-011), extending Principle V's explainability requirement to the enrollment decision, not just grading/sequencing decisions. | PASS |
| VI. A2A justified by concrete need | Not implicated -- no new agent or service boundary. | N/A |
| VII. Spec before code | This is that spec, approved per this milestone's own Definition of Done before Milestone 7 proper's implementation work begins (see spec.md's framing). | PASS |
| VIII. No real learner data | This spec *is* Principle VIII's required gate. FR-001/FR-008's automated checks are what make "no real learner data yet" a verified fact rather than an assumption. | PASS (this is the gate) |
| IX. Deployable and demoable | The gate script runs inside the existing `backend/` Vercel project's CI, no new deployment unit. Nothing about this spec changes what's deployed or demoable. | PASS |
| X. Staged release discipline | Feature branch `009-privacy-retention` -> PR into `staging`, same as every other feature. | PASS |

No violations requiring Complexity Tracking.

**Post-Phase-1 re-check**: `data-model.md`'s six entities remain
forward-looking (no migration, research.md §4); `data-classification.md`
and `quickstart.md` are documentation only. No new Constitution
exposure introduced by Phase 1 design -- the table above still holds
unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/009-privacy-retention/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── data-classification.md # Phase 1 output -- FR-002's written classification
├── quickstart.md         # Phase 1 output
└── tasks.md               # Phase 2 output (/speckit-tasks, not this command)
```

No `contracts/` directory -- this spec introduces no external API
surface of its own (Milestone 7 proper's future account/roster API is
a different spec's contract to define).

### Source Code (repository root)

```text
backend/
├── scripts/
│   └── check_no_real_account_path.py   # NEW -- FR-001/FR-008's gate,
│                                          # same style as check_no_subject_conditionals.py
└── tests/
    └── unit/
        └── test_check_no_real_account_path.py  # NEW -- imports the gate
                                                  # function directly; this IS
                                                  # the CI wiring (research.md §2),
                                                  # no .github/workflows/ change
```

**Structure Decision**: Single new script + test in the existing
`backend/` project, matching the pattern already established by
`check_no_subject_conditionals.py` for a different Constitution
principle's gate -- including that gate's own CI-wiring mechanism (a
pytest import), not a new workflow step. No new deployable unit, no
frontend change.

## Complexity Tracking

No violations -- table not needed.
