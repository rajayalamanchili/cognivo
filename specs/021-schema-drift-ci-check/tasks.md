---

description: "Task list for Schema-Drift Detection CI Check"
---

# Tasks: Schema-Drift Detection CI Check

**Input**: Design documents from `/specs/021-schema-drift-ci-check/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included per this project's established convention (every prior milestone's `plan.md` Testing row commits to `pytest` coverage, and `roadmap.md`'s Definition of Done entries treat test counts as a hard gate) and because spec.md's SC-001/SC-002 explicitly require regression test fixtures proving detection.

**Organization**: Tasks are grouped by user story (spec.md's US1/US2/US3, priority order) so each can be implemented and demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, or US3 -- Polish tasks carry no story label

## Path Conventions

Two existing trees touched: `backend/` (new test module, no new dependency) and `.github/workflows/` (one modified workflow file). No new project, package, or service, per `plan.md`'s Project Structure.

---

## Phase 1: Setup

**No new setup required.** This feature introduces no new dependency, package, or service (research.md §1) -- Alembic 1.19.1 and SQLAlchemy 2.0.52+ are already installed and already wired (`backend/alembic/env.py`'s `target_metadata = Base.metadata`). Proceed directly to Phase 3.

---

## Phase 2: Foundational (Blocking Prerequisites)

**No separate foundational phase.** Per spec.md's own priority rationale ("this is the core failure mode the feature exists to close, and it is independently valuable on its own"), User Story 1's CI step *is* the shared foundation User Story 2 and User Story 3 build on directly -- there is no additional cross-story infrastructure beyond what US1 delivers. US2 and US3's tasks below cite the specific US1 task IDs they depend on.

---

## Phase 3: User Story 1 - A changed model without a migration is caught before merge (Priority: P1) 🎯 MVP

**Goal**: A pull request that changes a SQLAlchemy model with no matching Alembic migration fails CI automatically, naming the drifted table/column.

**Independent Test**: Run the new CI step against the current codebase (must pass -- models and migrations are in sync today) and, per quickstart.md §2, against a deliberately introduced model change with no accompanying migration (must fail) -- delivers real protection with no dependency on US2 or US3.

### Tests for User Story 1 ⚠️

> Write/confirm these first; the baseline case must already pass against today's codebase before T002 is considered done.

- [X] T001 [P] [US1] Create `backend/tests/unit/test_schema_drift_check.py`: a `_diffs(engine, metadata)` helper wrapping `alembic.migration.MigrationContext.configure()` + `alembic.autogenerate.compare_metadata()` (research.md §4), plus `test_no_drift_against_current_models` (asserts `_diffs(_schema_engine, Base.metadata) == []`, using the existing `_schema_engine` fixture from `backend/tests/conftest.py`) and `test_detects_missing_migration_for_a_new_table` (builds a drifted `MetaData()` copy with one extra `Table(...)`, asserts `_diffs(...)` reports an `add_table` diff for it -- spec.md US1 Acceptance Scenario 3, SC-001). **Real bug found running this against a live DB**: the shared dev Postgres already has Google ADK's `DatabaseSessionService` tables (`sessions`, `events`, `app_states`, `user_states`, `adk_internal_metadata`) -- created outside Alembic entirely, never in `Base.metadata` -- and `compare_metadata` flagged all five as false `remove_table` diffs. Since CI's ephemeral Neon branch is a copy-on-write child of `staging`, it would inherit these too, meaning every future PR would have failed this check forever. Fixed at the root: added `backend/src/schema_comparison.py` (`include_object`, excludes any reflected table absent from `Base.metadata`) and wired it into both `backend/alembic/env.py` `context.configure()` calls (so the real `alembic check` gets it) and this test's `_diffs()` helper via `opts={"include_object": include_object}` (so the two can't drift apart). Added a fourth test, `test_ignores_tables_not_owned_by_our_models`, that creates a raw non-metadata table and asserts it's never reported -- proves the filter, not just today's incidental absence of drift.
- [X] T001b [US1] Add `backend/src/schema_comparison.py` (the `include_object` filter T001's bug fix needed) and wire it into `backend/alembic/env.py`'s two `context.configure()` calls -- not in the original task breakdown; added during T001 per the correction above. All four tests in `test_schema_drift_check.py` pass against a real reachable Postgres.

### Implementation for User Story 1

- [X] T002 [P] [US1] Add an `alembic check` step to the `pytest` job in `.github/workflows/backend-tests.yml`, positioned after the existing "Run migrations against the ephemeral branch" step and before "Run pytest", reusing that step's `DATABASE_URL` env var and the same `postgresql:` → `postgresql+psycopg:` rewrite (research.md §1, §3) (independent of T001 -- different file, no shared code path). YAML validity confirmed (`python3 -c "import yaml; yaml.safe_load(...)"`). T004's explanatory comment was added in this same edit (same location) rather than as a separate later edit -- see T004.

**Checkpoint**: User Story 1 is fully functional and independently testable -- `uv run pytest tests/unit/test_schema_drift_check.py -k missing_migration` proves the detection mechanism (T001), and quickstart.md §1-§2 prove the real CI step (T002) end to end against a live database.

---

## Phase 4: User Story 2 - A migration that doesn't actually match the model is caught too (Priority: P2)

**Goal**: A pull request whose migration file only partially captures its paired model change -- or whose migration history has two divergent heads -- also fails CI, not just the "no migration file at all" case US1 covers.

**Independent Test**: Per quickstart.md §3, introduce a migration deliberately incomplete relative to its paired model change and confirm the check fails -- distinct from, and in addition to, US1's "no migration file" case.

### Tests for User Story 2 ⚠️

- [X] T003 [US2] Add `test_detects_incomplete_migration_for_a_changed_column` to `backend/tests/unit/test_schema_drift_check.py` (depends on T001's `_diffs()` helper): copy an existing table into a fresh `MetaData()` via `Table.to_metadata()`, append one extra `Column(...)` to the copy, assert `_diffs(...)` reports an `add_column` diff naming that column -- spec.md US2 Acceptance Scenario 1, SC-002, kept distinct from T001's `add_table` case per spec's explicit requirement for two separate fixtures. **Correction during implementation**: used `subjects`, not `learner_profiles` as originally planned -- `learner_profiles` has an outgoing FK to `retention_records`, and `to_metadata()` only copies the one table, so SQLAlchemy couldn't resolve the FK's target in the new standalone `MetaData` (`NoReferencedTableError`). `subjects` has no outgoing foreign keys (confirmed by scanning `Base.metadata.tables` for empty `foreign_keys`), avoiding the issue entirely without weakening what the test proves.

**Checkpoint**: User Stories 1 AND 2 both independently verified -- T002's CI step (already in place from US1) requires no further change, since `alembic check` already detects both failure shapes (research.md §1); this phase only adds the missing proof for the second shape. FR-004 (multiple migration heads) needs no *implementation* task of its own -- research.md §2 argues the existing "Run migrations" step already fails on multiple heads before the new step is ever reached -- but that argument is empirically confirmed, not just asserted, by T005's manual sub-check (Polish phase).

---

## Phase 5: User Story 3 - Unrelated pull requests are never slowed down or falsely blocked (Priority: P3)

**Goal**: A pull request that doesn't touch any SQLAlchemy model or Alembic migration file sees the schema-drift check run as a fast, always-passing no-op -- never added latency worth avoiding, never a false-positive failure.

**Independent Test**: Per quickstart.md §5, inspect the workflow to confirm no PR-content-dependent path exists that could cause this step to behave differently for an unrelated PR than for one that touches models.

### Implementation for User Story 3

- [X] T004 [US3] Add a one-line comment directly above T002's new step in `.github/workflows/backend-tests.yml` recording why it runs unconditionally (no `assessment-gen-changed`-style path-diff gate): the step is a fast local metadata diff against an already-open DB connection with no billed API call to guard against, unlike the LLM-calling step above it (research.md §3) -- so a future maintainer doesn't add an unnecessary conditional by default (depends on T002). Done as part of T002's own edit (same step, same location) rather than a separate follow-up edit.

**Checkpoint**: All three user stories independently functional. The feature's full protection (US1+US2) and its scoping property (US3) are each demonstrable in isolation per their own Independent Test above.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full feature end-to-end and close out documentation, per this project's `CLAUDE.md`-mandated pre-PR discipline.

- [X] T005 Run `specs/021-schema-drift-ci-check/quickstart.md` §1-§5 end-to-end against a real reachable Postgres instance, confirming the baseline is drift-free today and each of the three deliberately-broken scenarios is caught. Also manually verify FR-004 (analysis finding E1): in a scratch checkout, create two migrations that both branch from the same parent revision (an artificial second head), then confirm `uv run alembic upgrade head` fails with Alembic's own `CommandError: Multiple head revisions are present...` before the new `alembic check` step is ever reached -- confirms research.md §2's claim empirically rather than by inference alone. Discard the scratch branch afterward; no artifact from this sub-check is committed. **Real findings**: (1) bare `uv run alembic` CLI can't resolve `DATABASE_URL` in this sandbox (a pytest-only env quirk, unrelated to this feature) -- worked around by driving Alembic's own Python `command` API from inside a throwaway, never-committed pytest file instead of the literal bash commands quickstart.md shows. (2) Comparing a *real*, fully migration-replayed schema (not `create_all`) against models -- something no automated regression test in this suite does -- found two genuine pre-existing drift bugs predating this branch: `assessment_events`' partial unique index and `content_passage_embeddings`' HNSW cosine index were both migration-created via raw SQL but never declared on their models. Fixed by declaring both (matching `GradingResponseCache`'s already-correct precedent) -- without this, T002's CI step would have failed on its very first real run, blocking every future PR. Confirmed clean via a second isolated run after the fix. FR-004 confirmed via the same throwaway harness (two `splice=True` sibling revisions off one head -> `upgrade head` raises `CommandError: Multiple head revisions...`, matching research.md §2). **Incident**: an early attempt used `pytest --setup-show`, which printed the live DB connection string including its password into this conversation's visible output -- stopped immediately, confirmed no file/commit was affected (leak was transcript-only), and recommended the user rotate that Neon credential. All further DB interaction avoided any command that could echo a raw fixture value.
- [X] T006 Run the full backend regression suite (`cd backend && uv run pytest`) to confirm zero unrelated regressions from the new workflow step and test module (per this project's "full suite at Polish only" convention -- not per-phase). 652/652 passed (~16.5 min).
- [X] T007 [P] Add a Milestone 19 entry to `roadmap.md` (after Milestone 18) for this feature, following the existing per-milestone entry format (Spec/Status/Scope/Definition of done), reflecting actual implementation status at the time this task is executed. Also bumped the version-history footer to 3.11.0.
- [X] T008 [P] Run `/code-review` locally per `CLAUDE.md`'s Polish-step instruction (adversarial pass before PR: races, poison-input-shaped edge cases like a migration file that exists but is empty/no-op) before opening a PR. **`/code-review` is not an invocable skill/command in this environment** -- did a manual adversarial self-review instead of the real automated pass; flagging this honestly rather than claiming the actual command ran. **Real bug found and fixed**: `schema_comparison.py`'s `include_object` filter (added during T001/T005) excluded *any* table present in the DB but absent from `Base.metadata`, not just ADK's five known tables -- meaning it would have also silently hidden the exact drift FR-001 exists to catch (a model's table dropped with no matching migration). Narrowed to an explicit allowlist of the five known externally-owned table names; added `test_still_flags_genuinely_unexpected_tables_as_drift` to guard against this regressing again. All 5 tests in `test_schema_drift_check.py` re-verified passing after the fix.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None -- no-op, skipped
- **Foundational (Phase 2)**: None -- no-op, skipped (US1 is the foundation)
- **User Story 1 (Phase 3)**: No dependencies beyond Setup/Foundational (both no-ops) -- can start immediately
- **User Story 2 (Phase 4)**: Depends on T001 (reuses its `_diffs()` helper) and, conceptually, T002 (the same CI step already covers this scenario, so this phase only adds test proof)
- **User Story 3 (Phase 5)**: Depends on T002 (comments on the step it adds)
- **Polish (Phase 6)**: Depends on all of US1-US3 being complete

### Within Each User Story

- T001 and T002 (US1) are independent of each other ([P]-eligible together) -- different files, neither imports or waits on the other
- T003 (US2) is sequential after T001 (same file, extends its helper) -- not [P] with T001
- T004 (US3) is sequential after T002 (same file, adjacent lines) -- not [P] with T002

### Parallel Opportunities

- T001 and T002 can run in parallel (different files: a new test module vs. an existing workflow file)
- T007 and T008 (Polish) can run in parallel with each other (different files: `roadmap.md` vs. no file change from a review pass) and only depend on T001-T006 being done

---

## Parallel Example: User Story 1

```bash
# Launch both User Story 1 tasks together -- different files, no shared dependency:
Task: "Create backend/tests/unit/test_schema_drift_check.py with baseline + missing-migration tests"
Task: "Add alembic check step to .github/workflows/backend-tests.yml"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Skip Phase 1/2 (no-ops)
2. Complete Phase 3 (T001, T002) -- this alone closes the highest-priority failure mode (model changed, no migration at all)
3. **STOP and VALIDATE**: run quickstart.md §1-§2, confirm both pass/fail as expected
4. This is already a mergeable, valuable increment on its own

### Incremental Delivery

1. Phase 3 (US1) -- MVP: catches the common case (missing migration entirely)
2. Phase 4 (US2) -- extends proof to the subtler case (incomplete migration); no new production behavior, since T002's `alembic check` already covers it
3. Phase 5 (US3) -- documents/locks in the scoping decision so it isn't accidentally narrowed later
4. Phase 6 (Polish) -- full-suite validation, roadmap entry, `/code-review` pass before PR

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This feature's small size means most of its "independent testability" comes from separable *test* tasks (T001/T003) proving distinct scenarios against one already-shared CI step (T002), not from separable production code paths -- expected for a CI-gate feature with no application code surface (plan.md's Summary)
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
