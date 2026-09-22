# Implementation Plan: Schema-Drift Detection CI Check

**Branch**: `031-schema-drift-ci-check` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/021-schema-drift-ci-check/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Add a CI gate that fails a pull request when the checked-in SQLAlchemy
models drift from what the checked-in Alembic migration history
actually produces -- closing the exact risk `tech-stack.md`'s
"Migrations per environment" row already names (a `staging` → `main`
promotion shipping against a schema nobody actually migrated). Per
research.md §1, the entire detection mechanism is Alembic's own,
already-installed `alembic check` command; no custom diffing script is
written. The only changes are one new step in the existing
`backend-tests.yml` `pytest` job (after migrations run, before tests
run) and one new pytest regression module that exercises the same
public comparison API directly.

## Technical Context

**Language/Version**: Python 3.12 (`backend/pyproject.toml`'s
`requires-python = ">=3.12"`) -- unchanged, no new language surface.

**Primary Dependencies**: Alembic 1.19.1 and SQLAlchemy 2.0.52+, both
already installed (`backend/pyproject.toml`). No new dependency added.

**Storage**: PostgreSQL (Neon) -- the check runs against the same
ephemeral per-PR Neon branch `backend-tests.yml` already creates and
migrates; no second database is provisioned.

**Testing**: pytest, reusing `backend/tests/conftest.py`'s existing
`_schema_engine`/`database_available` fixtures (real-Postgres,
skip-not-fail when unreachable).

**Target Platform**: GitHub Actions (`ubuntu-24.04`), the same runner
`backend-tests.yml`'s `pytest` job already uses.

**Project Type**: Web application (existing `backend/` + `frontend/`
split) -- this feature only touches `backend/` and
`.github/workflows/`.

**Performance Goals**: Near-zero added CI time on any PR (research.md
§3) -- one local metadata-reflection diff against an already-open DB
connection, no network calls beyond the DB itself, no LLM calls.

**Constraints**: Must not require any new secret/credential beyond what
`backend-tests.yml` already provisions (`NEON_API_KEY`, the ephemeral
branch's `DATABASE_URL`); must not provision a second Neon branch for
this check alone.

**Scale/Scope**: One CI workflow step, one pytest module. No production
runtime code changes, no new database objects, no new dependency.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature has no learner/instructor-facing surface, no agent
invocation, and no new persisted data -- most principles are not
engaged. Explicitly checked:

| Principle | Applicability | Result |
|---|---|---|
| I-II (personalization model, rubric grading) | N/A -- no mastery model or grading surface touched | Pass (not engaged) |
| III (One Engine, Many Subjects) | N/A -- no subject-specific logic anywhere in this feature | Pass (not engaged) |
| IV, VI (agent boundaries, A2A) | N/A -- no agent, no A2A service | Pass (not engaged) |
| V (logged/explainable decisions, tracing) | N/A -- no personalization/grading decision or agent invocation to log or trace | Pass (not engaged) |
| VII (spec before code) | Directly applicable | Pass -- this plan follows an approved `spec.md`; `tasks.md` follows this plan |
| VIII (no real learner data) | N/A -- touches no learner data at all, only CI/schema tooling | Pass (not engaged) |
| IX (deployable/demoable on Vercel) | Applicable in spirit: must not assume a persistent process | Pass -- runs as a bounded GitHub Actions CI step, not a deployed service; doesn't touch the Vercel deployment at all |
| X (staged release discipline) | Directly applicable | Pass, and reinforcing -- this feature *becomes* one more required automated check every PR into `staging`/`main` must pass, per `tech-stack.md`'s existing "Merge gate" row |

No violations. Complexity Tracking table below is empty/omitted.

## Project Structure

### Documentation (this feature)

```text
specs/021-schema-drift-ci-check/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature exposes no API, UI, or CLI
surface of its own (quickstart.md's header note) -- it's a CI-internal
gate over an existing relationship (models vs. migrations), not an
interface any caller integrates against.

### Source Code (repository root)

Existing web-application structure (`backend/` + `frontend/`) is
unchanged; this feature only adds files within `backend/` and
`.github/workflows/`, touching neither `frontend/` nor any other
milestone's existing code:

```text
backend/
├── alembic/
│   ├── env.py                              # MODIFIED -- wires include_object into both context.configure() calls
│   └── versions/                           # unchanged -- no new migration ships with this feature
├── src/
│   ├── schema_comparison.py                # NEW -- shared include_object filter (T001b, found mid-implementation)
│   └── models/
│       ├── assessment_event.py             # MODIFIED -- declares a previously-undeclared partial unique index
│       └── content_passage_embedding.py    # MODIFIED -- declares a previously-undeclared HNSW cosine index
└── tests/
    └── unit/
        └── test_schema_drift_check.py      # NEW -- regression coverage (research.md §4)

.github/
└── workflows/
    └── backend-tests.yml                   # MODIFIED -- one new `alembic check` step (research.md §3)
```

**Structure Decision**: Web-application structure (Option 2), already
locked by every prior milestone. No new top-level directory, no new
package -- this feature is additive within `backend/`'s existing
`tests/unit/` convention plus one CI workflow edit.

**Note (updated post-implementation, per code-review)**: `env.py`, the
two model files, and `schema_comparison.py` were originally planned as
unchanged/nonexistent above -- they became MODIFIED/NEW mid-implementation
once T005's live-DB verification found two real pre-existing
model-vs-migration drift bugs (see `tasks.md` T005/T008 for the full
story). This section is updated here to match the actual shipped diff,
rather than left describing only what was planned before that was
discovered.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations -- table intentionally empty.
