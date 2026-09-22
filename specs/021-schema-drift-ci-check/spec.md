# Feature Specification: Schema-Drift Detection CI Check

**Feature Branch**: `031-schema-drift-ci-check`

**Created**: 2026-09-22

**Status**: Draft

**Input**: User description: "Schema-drift detection CI check"

## User Scenarios & Testing *(mandatory)*

<!--
  This feature has no learner- or instructor-facing surface -- its
  "users" are the developers/maintainers of this codebase, and its
  "user journeys" are engineering workflows (changing a SQLAlchemy
  model, writing a migration, reviewing a PR that touches either). This
  mirrors this project's existing precedent for engineering-process
  gates (spec 001's SC-004 subject-conditional scanner, spec 014's
  prompt-artifact scanner, spec 020's
  `check_deletion_cascade_coverage.py`) -- an automated CI check
  enforcing an architectural invariant, not a product feature with an
  end user.

  "Schema" here means the backend relational database schema (the
  SQLAlchemy ORM models and the Alembic migration history that is
  supposed to produce them) -- not Milestone 1's domain-agnostic
  content-artifact schema, and not any frontend type. See Assumptions.
-->

### User Story 1 - A changed model without a migration is caught before merge (Priority: P1)

A developer edits a SQLAlchemy model (adds a column, changes a type,
adds a table) but forgets to generate the corresponding Alembic
migration. Today this is only caught if a human reviewer notices the
omission by eye, or later, when `staging`/`main` silently diverges from
what the ORM expects -- exactly the risk `tech-stack.md`'s "Migrations
per environment" row already names as the reason migrations run
per-environment rather than being assumed to carry over. With this
feature, opening a pull request that changes a model without a matching
migration fails CI automatically, before a human reviewer has to catch
it by eye.

**Why this priority**: This is the core failure mode the feature exists
to close, and it is independently valuable on its own -- it requires
nothing from any other story to deliver real protection.

**Independent Test**: Can be fully tested by running the new check
against the current codebase (must pass, since models and migrations
are in sync today) and then against a deliberately introduced model
change with no accompanying migration (must fail) -- delivers real
value with no dependency on any other story.

**Acceptance Scenarios**:

1. **Given** the current codebase where every model change has a
   matching migration, **When** the schema-drift check runs, **Then**
   it passes with no drift reported.
2. **Given** a pull request that adds a column to an existing model
   with no new migration, **When** the check runs, **Then** it fails
   and blocks merge, naming the specific table and column that drifted.
3. **Given** a pull request that adds a new model/table with no new
   migration, **When** the check runs, **Then** it fails the same way.

---

### User Story 2 - A migration that doesn't actually match the model is caught too (Priority: P2)

A developer generates a migration file (or hand-writes one) for a model
change, but the migration doesn't fully or correctly capture that
change -- for example, an autogenerate run that missed a column because
it ran before the model edit was saved, or a hand-edited migration with
a typo in a column name. A migration file existing is not the same
guarantee as the migration actually reproducing the model's current
state. The check applies the full migration history to a real database
and compares the *resulting* schema against the models, not just
whether a migration file is present.

**Why this priority**: Extends User Story 1's protection to a subtler
version of the same failure -- ranked below it because a migration file
existing at all is the more common case this feature needs to handle,
and this story has nothing to compare against until that baseline
detection works.

**Independent Test**: Can be fully tested by introducing a migration
that is deliberately incomplete relative to its paired model change
(e.g. a migration that adds a table but omits one of its columns) and
confirming the check fails, distinct from and in addition to User Story
1's "no migration file at all" case.

**Acceptance Scenarios**:

1. **Given** a pull request with a migration file that only partially
   reflects its paired model change, **When** the check runs against a
   database migrated to that PR's history, **Then** it fails and names
   the specific remaining drift.
2. **Given** a pull request whose migration history has two divergent
   heads (e.g. two migrations both branching from the same parent, never
   merged), **When** the check runs, **Then** it fails, since
   `alembic upgrade head` cannot deterministically produce one intended
   schema in that state either.

---

### User Story 3 - Unrelated pull requests are never slowed down or falsely blocked (Priority: P3)

A developer opens a pull request that doesn't touch any SQLAlchemy
model or Alembic migration file at all (a frontend change, a prompt
change, a docs update). The schema-drift check does not run, or is a
fast no-op, and never fails for a reason unrelated to the PR's own
content -- mirroring how this repo's other path-scoped CI gates (the
prompt-versioning check, the Assessment-Generation regression gate) are
already scoped to only the PRs that could plausibly trigger them.

**Why this priority**: Not load-bearing for the feature's core
protection (User Stories 1-2 already deliver that), but necessary for
the check to be tolerable to live with on every PR long-term. Ranked
last because it's a scoping refinement, not new detection capability.

**Independent Test**: Can be fully tested by running CI against a pull
request that only changes a frontend file and confirming the
schema-drift step is skipped or completes with no drift, independent of
whether User Story 1/2's failure scenarios are also exercised.

**Acceptance Scenarios**:

1. **Given** a pull request that changes only frontend or documentation
   files, **When** CI runs, **Then** the schema-drift check step is
   skipped or completes as a fast no-op.
2. **Given** a pull request that changes backend code but not models or
   migrations, **When** the schema-drift check runs, **Then** it passes
   with no drift reported.

---

### Edge Cases

- What happens when a migration file exists and is syntactically valid,
  but running it against a fresh database raises its own error (e.g. a
  bad `op.` call)? The check's own migration-apply step fails first,
  which already blocks merge today via the existing "run migrations"
  CI step -- the drift check itself never gets to compare a broken
  migration's output.
- What happens when a PR both changes a model and generates a correct,
  complete migration for it? The check passes, same as any PR where
  models and migrations already agree.
- What happens when a PR changes a migration file that's already been
  applied to `staging`/`main` (edits history instead of adding a new
  migration)? Out of scope for this check specifically (drift
  detection, not migration-history-immutability enforcement) -- see
  Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: CI MUST detect any difference between the SQLAlchemy
  models' current state and the schema produced by applying every
  committed Alembic migration, for any pull request whose diff touches
  backend model or migration files.
- **FR-002**: CI MUST fail the pull request's check (not merely warn)
  when drift is detected, blocking merge the same way every other
  gate in `backend-tests.yml` already does.
- **FR-003**: The check MUST compare against a schema produced by
  actually applying the full migration history to a real database, not
  a static file-existence check, so it also catches a migration file
  that exists but doesn't fully reproduce the intended model state
  (User Story 2).
- **FR-004**: CI MUST also fail when the migration history has more
  than one head, since that state means `alembic upgrade head` cannot
  deterministically produce one intended schema either.
- **FR-005**: The check MUST be skipped, or complete as a fast no-op,
  for pull requests whose diff doesn't touch backend model or migration
  files (User Story 3), consistent with this repo's existing
  path-scoped gates.
- **FR-006**: A failing check MUST report which table(s)/column(s)
  drifted, not just that drift exists, so a maintainer can act on the
  failure without independently re-deriving what changed.
- **FR-007**: This check MUST run on every pull request targeting
  `staging` or `main` that isn't skipped by FR-005, consistent with
  Constitution Principle X's requirement that every PR in either
  direction pass its automated checks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pull request that changes a model without an
  accompanying migration is blocked from merging in 100% of cases,
  demonstrated by a regression test fixture that introduces exactly
  this condition and confirms the check fails.
- **SC-002**: A pull request that changes a migration incompletely
  relative to its paired model change is blocked from merging,
  demonstrated by a second, distinct regression test fixture (not
  satisfied by SC-001's "no migration file" case alone).
- **SC-003**: Pull requests that don't touch backend model or migration
  files see zero added CI time from this check and zero false-positive
  failures, verified against the current codebase's existing PRs/CI
  history.
- **SC-004**: When the check fails, the reported failure names the
  specific drifted table or column, verified by inspecting the check's
  output in at least one of SC-001/SC-002's regression fixtures.

## Assumptions

- "Schema drift" in this feature's scope means the backend relational
  database schema only -- the SQLAlchemy ORM models measured against
  the Alembic migration history that's supposed to produce them. It
  does not cover Milestone 1's domain-agnostic content-artifact schema
  (Pydantic models describing question/content JSON), nor any
  frontend/TypeScript type. This is the standard meaning of "schema
  drift" in a backend-CI context, and matches the specific drift risk
  `tech-stack.md`'s "Migrations per environment" row already names for
  this codebase's Neon branch-per-environment model.
- This check reuses the ephemeral-Neon-branch infrastructure
  `backend-tests.yml` already creates per PR (create branch → run
  migrations → run tests → tear down) rather than provisioning a
  second database environment just for this gate.
- This check only detects and blocks; it does not auto-generate or
  auto-fix a missing/incomplete migration. A human still writes and
  reviews the migration itself.
- No escape hatch or allowlist is needed (unlike
  `check_deletion_cascade_coverage.py`'s allowlist, which exists
  because some tables are legitimately excluded from cascade coverage):
  there is no legitimate case where a model change should ship without
  a matching migration, so the check has no override path.
- This check applies only going forward, to new pull requests -- it
  does not retroactively scan already-merged migration history on
  `staging`/`main`.
- Editing an already-applied migration file's history (rather than
  adding a new migration) is a different problem (migration-history
  immutability) and is out of scope for this feature.
