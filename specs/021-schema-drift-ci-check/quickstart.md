# Quickstart: Validating the Schema-Drift Detection CI Check

**Feature**: `031-schema-drift-ci-check` | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

No new API, UI, or CLI surface ships with this feature (see
research.md §1-§3 -- interface contracts are skipped for the same
reason: this is a CI-internal gate, not a project-facing interface).
This guide validates the CI step itself and its regression test.

## Prerequisites

- A reachable Postgres instance with `DATABASE_URL` set (e.g. a local
  Postgres, or an ephemeral Neon branch as CI itself uses). Every step
  below skips cleanly, not fails, if unset/unreachable -- same
  convention as `backend/tests/conftest.py`'s existing fixtures.
- `uv sync` already run in `backend/`.

## 1. Confirm the baseline is drift-free today

```bash
cd backend
DATABASE_URL="<your-url>" uv run alembic upgrade head
DATABASE_URL="<your-url>" uv run alembic check
```

**Expected**: `alembic check` exits 0 with no diff reported -- today's
migration history already matches today's models (spec.md's User Story
1 Acceptance Scenario 1).

## 2. Confirm it catches a missing migration (User Story 1)

```bash
cd backend
# Add a throwaway column to any model, e.g. src/models/learner_profile.py
# (a new nullable Column, no migration generated for it)
DATABASE_URL="<your-url>" uv run alembic check
```

**Expected**: non-zero exit, output naming the specific drifted
table/column (e.g. `New upgrade operations detected: ...
add_column('learner_profiles', ...)`). Revert the throwaway change
afterward -- this step is for manual verification only, not something
to commit.

## 3. Confirm it catches an incomplete migration (User Story 2)

```bash
cd backend
# Generate a migration for the same throwaway column, then delete one
# line from the generated upgrade() body before applying it
DATABASE_URL="<your-url>" uv run alembic upgrade head
DATABASE_URL="<your-url>" uv run alembic check
```

**Expected**: non-zero exit, same as step 2 -- drift is still detected
even though a migration file exists, because the *applied* schema still
doesn't match the models. Revert afterward.

## 4. Run the regression test suite

```bash
cd backend
DATABASE_URL="<your-url>" uv run pytest tests/unit/test_schema_drift_check.py -v
```

**Expected**: all cases pass, covering the same three scenarios above
via `alembic.autogenerate.compare_metadata()` directly (research.md
§4) -- no manual model editing required for this automated form.

## 5. Confirm unrelated PRs aren't slowed down (User Story 3)

Inspect `.github/workflows/backend-tests.yml`'s new `alembic check`
step: it sits inside the existing `pytest` job, which itself only runs
on PRs touching `backend/**` (the job's own `paths:` filter). No
additional path-diff conditional gates this specific step (research.md
§3) -- for a PR that doesn't touch models/migrations, the step runs and
passes in the time of one metadata reflection query, not a meaningfully
measurable addition to that job's total runtime.
