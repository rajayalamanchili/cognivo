#!/usr/bin/env python3
"""Fails if a table has a foreign key to `learner_profiles`,
`real_guardian_accounts`, or `real_instructor_accounts` that spec 020's
deletion cascade doesn't account for (SC-001).

data-model.md's cascade-order tables are the source of truth for what
`_delete_learner`/`_delete_guardian`/`_delete_instructor`
(`src/services/deletion/execute.py`) actually walk. This script doesn't
re-implement that logic -- it just makes sure no *new* table introduces
a direct FK to one of the three real-identity tables without either
being added to that cascade or explicitly allowlisted (matching
data-model.md's "Explicitly out of cascade scope" section), the same
regression-prevention shape `check_no_subject_conditionals.py` already
uses for a different Constitution gate.

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

# Tables whose FK to a target table is reached by execute.py's cascade
# functions, per data-model.md's cascade-order tables.
HANDLED_TABLES = {
    "assessment_events",
    "enrollments",
    "enrollment_requests",
    "generated_questions",
    "grade_progress",
    "learner_profiles",
    "mastery_states",
    "quiz_assignments",
    "quiz_assignment_targets",
    "quiz_sessions",
    "tutoring_sessions",
}

# Tables that reference a target table's identity but deliberately carry
# no data this feature needs to erase (data-model.md's "Explicitly out
# of cascade scope"). Empty today -- every current direct FK is handled
# above -- kept as the place a future exception gets documented rather
# than silently added to HANDLED_TABLES.
ALLOWLISTED_TABLES: set[str] = set()


def main() -> int:
    violations = set()
    for table in Base.metadata.tables.values():
        if table.name in HANDLED_TABLES or table.name in ALLOWLISTED_TABLES:
            continue
        for fk in table.foreign_keys:
            if fk.column.table.name in TARGET_TABLES:
                violations.add(f"{table.name}.{fk.parent.name} -> {fk.column.table.name}")

    if violations:
        print("FAIL: FK(s) to a real-identity table with no cascade coverage or allowlist entry:")
        for violation in sorted(violations):
            print(f"  - {violation}")
        print(
            "Add the referencing table to execute.py's cascade (and HANDLED_TABLES above), "
            "or to ALLOWLISTED_TABLES with a comment explaining why it carries no data to erase."
        )
        return 1

    print(f"OK: every FK to {sorted(TARGET_TABLES)} is handled by the deletion cascade")
    return 0


if __name__ == "__main__":
    sys.exit(main())
