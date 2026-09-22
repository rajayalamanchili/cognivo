"""Shared Alembic autogenerate/check filter (spec 021).

Imported by both `alembic/env.py` (the real migration/check path) and
`tests/unit/test_schema_drift_check.py` (the regression proof), so the
two can never silently drift apart from each other.
"""

# Google ADK's DatabaseSessionService (tech-stack.md's ADK session/state
# backing) creates these tables directly against this same Postgres
# database, outside Alembic entirely -- they exist in every real
# deployment's DB but are never in `Base.metadata`. Last confirmed
# against installed google-adk (2.7.x): sessions, events, app_states,
# user_states, adk_internal_metadata (schemas.v0 + v1 combined).
_FALLBACK_EXTERNALLY_OWNED_TABLES = frozenset(
    {"sessions", "events", "app_states", "user_states", "adk_internal_metadata"}
)

try:
    # Preferred: derive from ADK's own schema modules (both its v0 and
    # v1 generations) rather than trust the hand-maintained fallback
    # above staying in sync -- so a routine google-adk version bump
    # that renames/adds/removes a session table updates this
    # automatically instead of silently drifting from reality.
    #
    # `schemas.v0`/`v1` reads as ADK-internal (undocumented as public
    # API), and pyproject.toml pins `google-adk>=2.7.0` with no upper
    # bound -- code-review flagged that a future release reorganizing
    # this path would otherwise break `alembic/env.py`'s import at
    # *every* real migration invocation, not just this CI check. The
    # try/except keeps that failure mode to "silently falls back to a
    # possibly-stale list" instead of "every real deployment's
    # migrations stop working."
    from google.adk.sessions.schemas.v0 import Base as _AdkSchemaV0
    from google.adk.sessions.schemas.v1 import Base as _AdkSchemaV1

    _EXTERNALLY_OWNED_TABLES = frozenset(_AdkSchemaV0.metadata.tables) | frozenset(
        _AdkSchemaV1.metadata.tables
    )
except ImportError:
    _EXTERNALLY_OWNED_TABLES = _FALLBACK_EXTERNALLY_OWNED_TABLES


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
