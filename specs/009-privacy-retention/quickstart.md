# Quickstart: Privacy & Retention Spec -- Validating the Gate

**Feature**: `009-privacy-retention` | **Date**: 2026-08-22

Validates this spec's two actual deliverables -- the automated
real-account gate script (FR-001/FR-008) and the written data
classification (FR-002). Does **not** validate Milestone 7 proper's
account/roster/dashboard features, since this spec builds none of them
(see plan.md's Summary).

## Prerequisites

- `backend/` dependencies installed (`uv sync`) -- the gate script uses
  only the Python standard library, but runs via the same `uv run`
  invocation as every other `backend/scripts/*.py` check.
- No live Postgres, no `ANTHROPIC_API_KEY` needed (research.md §2's
  design constraint).

## Validation scenario 1: the gate passes against the current codebase

`uv run python scripts/check_no_real_account_path.py` (from `backend/`)
-> exit code `0`, confirming no model in `backend/src/models/` matches
an account-like table name without a non-nullable `is_demo` column.
True today: only `DemoLearnerProfile` exists, and it already carries
`is_demo=True` (Milestone 1).

## Validation scenario 2: the gate fails on a synthetic violation

Add a throwaway model class to a scratch file under
`backend/src/models/` (e.g. `class Student(Base): __tablename__ =
"students"; student_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)`
-- no `is_demo` column) -> re-run the gate script -> non-zero exit,
error message naming the offending class and table. Delete the scratch
file afterward; this scenario is a one-time manual check during
`/speckit-implement`'s Polish phase, not a permanent fixture.

## Validation scenario 3: the gate fails, then passes once `is_demo` is added

Same scratch model as scenario 2, but with `is_demo: Mapped[bool] =
mapped_column(nullable=False, default=False)` added -> re-run -> exit
code `0`. Confirms the check's actual discriminating condition is the
`is_demo` column, not merely the table name.

## Validation scenario 4: the gate is wired into CI

Open a throwaway PR containing scenario 2's violation -> confirm
`backend-tests.yml`'s new step fails the PR's checks, before `pytest`
even runs (research.md §2's ordering choice) -> close the PR without
merging.

## Validation scenario 5: the data classification covers every FR-002 field

Manually cross-check `data-classification.md` against `data-model.md`'s
six entities -- confirm every field listed in `data-model.md` that
isn't purely a foreign key or primary key has a corresponding row in
`data-classification.md` with a non-empty retention period and
deletion trigger. (This is a documentation completeness check, not
something the gate script automates -- automating a doc-completeness
diff is more machinery than a spec this size warrants; a manual check
during `/speckit-implement`'s Polish phase, same as scenario 2, is
sufficient.)

## Not validated here (Milestone 7 proper's scope)

Deletion SLA timing (SC-002), cross-tenant access control (SC-003), and
demo-account distinguishability (SC-005) all require real accounts,
rosters, and a dashboard to exist -- none of which this spec builds.
Their validation belongs to whichever spec implements Milestone 7
proper's account/roster/dashboard features, using this spec's
requirements as its acceptance bar.
