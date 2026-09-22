"""Shared Alembic autogenerate/check filter (spec 021).

Imported by both `alembic/env.py` (the real migration/check path) and
`tests/unit/test_schema_drift_check.py` (the regression proof), so the
two can never silently drift apart from each other.
"""

from google.adk.sessions.schemas.v0 import Base as _AdkSchemaV0
from google.adk.sessions.schemas.v1 import Base as _AdkSchemaV1

# Google ADK's DatabaseSessionService (tech-stack.md's ADK session/state
# backing) creates these tables directly against this same Postgres
# database, outside Alembic entirely -- they exist in every real
# deployment's DB but are never in `Base.metadata`. Derived from ADK's
# own schema modules (both its v0 and v1 generations), not a hand-
# maintained literal list -- so a future google-adk version bump that
# renames/adds/removes a session table updates this automatically
# instead of silently breaking every PR with an unexplained false
# "remove_table" diff (code-review finding, spec 021 Polish).
_EXTERNALLY_OWNED_TABLES = frozenset(_AdkSchemaV0.metadata.tables) | frozenset(
    _AdkSchemaV1.metadata.tables
)


def include_object(object, name, type_, reflected, compare_to):
    """Exclude only the specific, known externally-owned tables above.

    Deliberately an explicit allowlist, not "ignore any table absent
    from Base.metadata" -- a blanket exclusion would also silently hide
    the exact drift shape FR-001 exists to catch: a table dropped from
    a model with no matching `drop_table` migration would just vanish
    from comparison instead of being flagged. Only these five specific,
    intentionally-external tables are exempt; any other reflected-but-
    unmapped table is still real drift and still reported.
    """
    if (
        type_ == "table"
        and reflected
        and compare_to is None
        and name in _EXTERNALLY_OWNED_TABLES
    ):
        return False
    return True
