# Research: Privacy & Retention Spec -- the Real Learner Data Gate

**Feature**: `009-privacy-retention` | **Date**: 2026-08-22

No `NEEDS CLARIFICATION` markers remained in `plan.md`'s Technical
Context -- every choice below was decided directly rather than left
open, but is documented here for the same reason every other spec's
research.md exists: so a later reader (or a future A2A/schema-drift-
style rediscovery) doesn't have to re-derive the reasoning.

## §1. Gate script design: AST inspection of SQLAlchemy models, not a source-text grep

**Decision**: `check_no_real_account_path.py` parses every `.py` file
under `backend/src/models/` with Python's `ast` module, finds every
class inheriting from the project's declarative `Base`
(`src/models/base.py`), and fails if any such class's table name
suggests a real-account concept (`learner`, `student`, `instructor`,
`teacher`, `guardian`, `parent`, `account`, `user` -- case-insensitive
substring match) unless that class declares a non-nullable `is_demo`
column -- non-nullability recognized from either an explicit
`nullable=False` keyword in a `mapped_column(...)` call, or a
`Mapped[bool]` annotation with no `Optional`/`| None` wrapper
(SQLAlchemy 2.0's own type-inferred non-nullability, revised from an
earlier draft of this check that only recognized the explicit keyword
and would have false-positived on a model correctly relying on type
inference instead, per `/speckit-analyze` finding F4, 2026-08-22).

**Rationale**: `check_no_subject_conditionals.py` (Principle III's
gate) greps `backend/src` for known subject-id string literals --
appropriate there because the forbidden pattern is a literal string.
Here the forbidden pattern is structural (a model shape), not textual:
a `RealLearnerAccount` class without `is_demo` is the violation,
regardless of what string literals appear near it. `ast` parsing
correctly finds every `Base`-subclassing class and its column
declarations without false-positiving on comments, docstrings, or an
unrelated variable named `learner_id` (which appears constantly today,
correctly, as a foreign key column on existing tables). A plain regex
over column names would either miss multi-line class bodies or need
its own mini-parser -- `ast` already is one.

**Alternatives considered**:
- *Runtime introspection* (import every model module, walk
  `Base.metadata.tables`): rejected because it requires the full
  SQLAlchemy/app import graph to succeed in CI (env vars, no live DB
  needed for metadata reflection, but still more moving parts than a
  pure-stdlib static scan that mirrors the existing Principle III gate
  script's zero-dependency design).
- *A denylist of exact table names*: rejected -- it would need updating
  every time a new real-account-shaped table is proposed, which is
  exactly the moment this gate is supposed to catch it, not the moment
  someone remembers to update a list.

## §2. CI wiring: a pytest test importing the check function, not a new workflow step

**Decision** (revised during `/speckit-implement`, 2026-08-22 -- see
below): wire `check_no_real_account_path.py` into CI the same way
`check_no_subject_conditionals.py` already is: a plain pytest test
(`backend/tests/unit/test_check_no_real_account_path.py`) that imports
`find_violations` directly and asserts it returns `[]`. No new
workflow step, no new workflow file -- `backend-tests.yml`'s existing
`pytest` step already discovers this test automatically
(`pyproject.toml`'s `testpaths = ["tests"]`), since a plain Python
import needs nothing a fresh `uv sync` doesn't already provide.

**Correction**: this section originally (Phase 0) claimed
`check_no_subject_conditionals.py` "is not currently wired into any
GitHub Actions workflow at all" and proposed a brand-new workflow step
for this spec's own gate as a result. That claim was wrong --
discovered only once actually writing this feature's test file and
finding `tests/unit/test_no_subject_conditionals.py` already exists,
importing `check_no_subject_conditionals.py`'s functions directly, and
running as part of the existing `pytest` step every PR already
triggers. `check_no_subject_conditionals.py` *is* CI-enforced; it's
just wired in as a test rather than a standalone script invocation.
This spec now follows that same, already-proven pattern instead of
inventing a second, redundant mechanism -- a case of not trusting an
earlier research note enough to re-verify it against the actual
codebase before building on it.

## §3. Data classification as a standalone Markdown file, not embedded in spec.md

**Decision**: FR-002's written data classification lives in its own
`data-classification.md` (Phase 1 output), not as a section inside
`spec.md` or `data-model.md`.

**Rationale**: `spec.md` describes behavior/requirements;
`data-model.md` describes entity shape for whoever implements Milestone
7 proper. The data classification (field-by-field retention period and
deletion trigger) is a third, distinct artifact -- closer to a living
compliance reference than a one-time design decision -- and keeping it
separate means it can be updated independently (e.g., when Milestone 7
proper's actual implementation reveals a field this spec didn't
anticipate) without churning the spec or data model themselves.

## §4. No new database tables in this spec

**Decision**: This spec creates no migrations. `data-model.md`'s six
entities are a forward-looking schema for whoever writes Milestone 7
proper's own `plan.md`, not something this plan persists.

**Rationale**: Per spec.md's own Assumptions, Milestone 7 proper (auth,
rosters, dashboard, content review) is explicitly a separate,
subsequent spec. Creating `RealLearnerAccount`/`RealGuardianAccount`/etc.
tables now, with no code path that ever writes to them, would be dead
schema sitting in production ahead of the feature that uses it --
exactly the kind of premature abstraction this project's own working
norms (CLAUDE.md: "Don't design for hypothetical future requirements")
warn against. The gate script (§1) is what makes it safe to defer the
actual tables: it fails loudly the moment someone *does* start adding
one before this spec's other requirements are met.
