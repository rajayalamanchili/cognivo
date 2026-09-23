#!/usr/bin/env python3
"""Fails if a *column* has a foreign key to `learner_profiles`,
`real_guardian_accounts`, or `real_instructor_accounts` that spec 020's
deletion cascade doesn't account for (SC-001).

data-model.md's cascade-order tables are the source of truth for what
`_delete_learner`/`_delete_guardian`/`_delete_instructor`
(`src/services/deletion/execute.py`) actually walk. This script doesn't
re-implement that logic -- it just makes sure no *new* FK column
introduces a direct reference to one of the three real-identity tables
without either being added to that cascade or explicitly allowlisted
(matching data-model.md's "Explicitly out of cascade scope" section),
the same regression-prevention shape `check_no_subject_conditionals.py`
already uses for a different Constitution gate.

Deliberately column-, not table-, granular (PR #79 review): a table can
carry more than one FK into a target table (e.g. `tutoring_sessions`
has both `learner_id` and `guardian_id`), and each one needs its own
entry -- a table being "handled" for one column says nothing about
whether a different column on that same table is actually walked.

Walks the SQLAlchemy ORM metadata directly (`src/models/__init__.py`'s
`Base.metadata`) rather than a live database -- every FK the schema
will ever create is already declared there, so this needs no
`DATABASE_URL` and stays exact as new tables/migrations are added.

Known limitation: this only catches *declared* `ForeignKey` columns.
A handful of columns in this schema (`classroom_rosters.instructor_id`,
`retention_records.account_id`, `deletion_requests.target_id`) are
deliberately *not* real FKs -- see each model's own docstring for why --
so a hypothetical future soft reference of that same shape wouldn't be
caught here either. That's an accepted gap, not something this script
tries to solve.

Usage: python scripts/check_deletion_cascade_coverage.py
Exit code 0 = every direct FK accounted for; 1 = a gap found.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.models import Base  # noqa: E402

TARGET_TABLES = {"learner_profiles", "real_guardian_accounts", "real_instructor_accounts"}

# (table, column) pairs whose FK to a target table is reached by
# execute.py's cascade functions, per data-model.md's cascade-order
# tables. Column-, not table-, granular: a table can carry more than
# one FK into a target table, and each needs its own entry.
HANDLED_COLUMNS = {
    ("assessment_events", "learner_id"),
    ("enrollments", "learner_id"),
    ("enrollment_requests", "learner_id"),
    ("generated_questions", "learner_id"),
    ("generated_questions", "flagged_by"),
    ("grade_progress", "learner_id"),
    ("learner_profiles", "guardian_id"),
    ("mastery_states", "learner_id"),
    ("practice_sessions", "learner_id"),
    ("quiz_assignments", "instructor_id"),
    ("quiz_assignment_targets", "learner_id"),
    ("quiz_sessions", "learner_id"),
    ("tutoring_sessions", "learner_id"),
    ("tutoring_sessions", "guardian_id"),
}

# (table, column) pairs that reference a target table's identity but
# deliberately carry no data this feature needs to erase (data-model.md's
# "Explicitly out of cascade scope"). Empty today -- every current
# direct FK is handled above -- kept as the place a future exception
# gets documented rather than silently added to HANDLED_COLUMNS.
ALLOWLISTED_COLUMNS: set[tuple[str, str]] = set()


def find_violations() -> list[str]:
    """Every direct FK column to a real-identity table (`TARGET_TABLES`)
    that isn't in `HANDLED_COLUMNS`/`ALLOWLISTED_COLUMNS`, sorted for
    stable output. Empty means SC-001's gate holds."""
    violations = set()
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if fk.column.table.name not in TARGET_TABLES:
                continue
            key = (table.name, fk.parent.name)
            if key in HANDLED_COLUMNS or key in ALLOWLISTED_COLUMNS:
                continue
            violations.add(f"{table.name}.{fk.parent.name} -> {fk.column.table.name}")
    return sorted(violations)


def main() -> int:
    violations = find_violations()

    if violations:
        print("FAIL: FK(s) to a real-identity table with no cascade coverage or allowlist entry:")
        for violation in violations:
            print(f"  - {violation}")
        print(
            "Add the referencing column to execute.py's cascade (and HANDLED_COLUMNS above), "
            "or to ALLOWLISTED_COLUMNS with a comment explaining why it carries no data to erase."
        )
        return 1

    print(f"OK: every FK to {sorted(TARGET_TABLES)} is handled by the deletion cascade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
