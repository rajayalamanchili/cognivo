# Phase 0 Research: Schema-Drift Detection CI Check

**Feature**: `031-schema-drift-ci-check` | **Date**: 2026-09-22

No `[NEEDS CLARIFICATION]` markers exist in `spec.md` (its Assumptions
section already resolved the one real ambiguity -- which "schema" this
covers). This document instead records the concrete technical decisions
Technical Context needed, each confirmed directly against this
repo's actual dependencies rather than assumed.

## 1. Detection mechanism: Alembic's own `check` command, not custom code

**Decision**: Use Alembic's built-in `alembic check` CLI command as the
CI gate itself. No new custom schema-diffing script.

**Rationale**: `backend/pyproject.toml` already pins `alembic>=1.19.1`
(confirmed installed: `alembic 1.19.1`), and `alembic check` (available
since Alembic 1.9, 2022) does exactly FR-001/FR-002/FR-003/FR-006:
connects to a real, migrated database, runs the same autogenerate
comparison `alembic revision --autogenerate` uses, and exits non-zero
with a human-readable diff (e.g. `New upgrade operations detected:
add_column('learner_profiles', ...)`) if the live schema doesn't match
`Base.metadata`. `backend/alembic/env.py` already sets
`target_metadata = Base.metadata` for both online and offline mode, so
the command works against this codebase with zero configuration
changes. Confirmed locally: running `uv run alembic check` without a
reachable `DATABASE_URL` fails with the same connection error
`alembic upgrade head` would (`NoSuchModuleError` from an empty/invalid
URL) -- i.e. it has the exact same "needs a real migrated DB" shape as
the migration step already in `backend-tests.yml`, not a new kind of
dependency.

**Alternatives considered**:
- *A custom `backend/scripts/check_*.py` script*, matching this repo's
  existing precedent (`check_deletion_cascade_coverage.py`,
  `check_no_subject_conditionals.py`, etc.). Rejected: every one of
  those existing scripts wraps *custom* logic (walking ORM FK metadata,
  scanning source for `subject_id` conditionals) that doesn't already
  exist as a maintained tool. Schema-vs-migration drift detection does
  already exist, fully implemented and tested upstream, as `alembic
  check` -- writing a wrapper around it would only reformat output
  Alembic already produces, for no behavioral gain. This is the one
  check in this family where the "already-installed dependency solves
  it" step wins outright over "match the existing pattern."
- *`alembic revision --autogenerate --check` in a dry-run mode with
  manual diff parsing*: `alembic check` already is this, packaged as a
  single command with a clean exit code -- no reason to reimplement it
  via the lower-level `revision` command.

## 2. Multiple migration heads (FR-004): already covered, no new logic needed

**Decision**: No separate multi-head detection is needed. The existing
"Run migrations against the ephemeral branch" step in
`backend-tests.yml` (`alembic upgrade head`) already fails on multiple
heads today -- Alembic raises `CommandError: Multiple head revisions
are present for given argument 'head'` when `head` is ambiguous. Since
the new `alembic check` step runs *after* that step (§3), a multi-head
history never reaches it; the pipeline already fails one step earlier.

**Rationale**: FR-004 is a property of the pipeline's step ordering, not
new code. Documenting this here (rather than in a script) keeps the
check itself minimal and avoids duplicating a failure mode Alembic
already surfaces on its own.

## 3. CI placement and scoping (FR-005, FR-007): unconditional step, no path filter

**Decision**: Add one new step to the existing `pytest` job in
`.github/workflows/backend-tests.yml`, positioned after "Run migrations
against the ephemeral branch" and before "Run pytest": `uv run alembic
check` (with the same `postgresql:` → `postgresql+psycopg:` URL rewrite
the migration step already applies). No new path-diff conditional step
(unlike the existing `assessment-gen-changed` gate).

**Rationale**: The workflow already only triggers on PRs touching
`backend/**` (its top-level `paths:` filter), and the "Run migrations"
step it follows already runs unconditionally on every such PR today,
regardless of whether models or migrations changed. `alembic check` is
a local metadata-reflection diff against an already-open DB connection
-- no LLM call, no meaningful added latency -- unlike the
`assessment-gen-changed`-gated step, which exists specifically to avoid
spending real, billed LLM API calls on PRs that don't need them. Adding
a second git-diff conditional here would be complexity with no
corresponding cost to avoid: for any PR that doesn't touch models or
migrations, the step runs and passes near-instantly (SC-003's "zero
added CI time... zero false positives" is satisfied by the check being
fast and correct, not by skipping it). This is the "does this need to
exist at all" rung of the usual complexity ladder resolving to "no" for
the scoping logic specifically, even though the check itself is
needed.

## 4. Regression-test approach (SC-001/SC-002): exercise `compare_metadata` directly, not a second ephemeral DB

**Decision**: Add one pytest module
(`backend/tests/unit/test_schema_drift_check.py`) that calls
`alembic.autogenerate.compare_metadata()` -- the same public API
`alembic check` wraps internally -- directly against the real Postgres
connection this suite's existing `_schema_engine` fixture
(`backend/tests/conftest.py`) already provides, rather than
orchestrating a second full `alembic upgrade head` replay inside a unit
test.

**Rationale**: `_schema_engine` already builds a real, live schema
(`Base.metadata.create_all`) each test session and already
skips cleanly (not fails) when no `DATABASE_URL` is reachable --
reusing it means this feature needs zero new DB-fixture machinery. The
test asserts:
1. `compare_metadata` against the current, unmodified `Base.metadata`
   returns no diffs (guards against a false-positive-prone
   `compare_metadata` misconfiguration going undetected -- directly
   serves SC-003).
2. `compare_metadata` against a deliberately drifted copy of the
   metadata (an entirely new table, simulating User Story 1's "model
   changed, no migration exists at all") reports that table as an
   addition -- serves SC-001.
3. `compare_metadata` against a deliberately drifted copy of one
   already-present table (an added column, simulating User Story 2's
   "migration exists but doesn't fully capture the change") reports
   that column as an addition -- serves SC-002, distinctly from (2).

This intentionally does not re-verify that real, checked-in Alembic
migrations reproduce `Base.metadata` when replayed from scratch -- that
end-to-end invariant is what the actual `alembic check` CI step (§3)
verifies for real, on every PR, against a genuinely migrated ephemeral
Neon branch. A unit test replaying full migration history would
duplicate that coverage at unit-test cost/fragility for no added
protection.

**Alternatives considered**:
- *Spin up a second ephemeral database in the test session and run
  `alembic upgrade head` against it before diffing*: rejected as
  redundant with what CI's own new step already proves live, and adds
  real complexity (a second migration replay, cleanup, and a fixture
  ordering hazard against the existing session-scoped `_schema_engine`
  fixture, which already drops/recreates the same physical database's
  schema via `create_all`).
- *Shell out to the actual `alembic check` CLI as a subprocess in the
  test*: rejected -- slower, and `compare_metadata` is the documented
  public API the CLI itself calls, so calling it directly is not a
  weaker test, just a more direct one.
