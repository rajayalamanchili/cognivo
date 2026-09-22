"""Shared Alembic autogenerate/check filter (spec 021).

Imported by both `alembic/env.py` (the real migration/check path) and
`tests/unit/test_schema_drift_check.py` (the regression proof), so the
two can never silently drift apart from each other.
"""


def include_object(object, name, type_, reflected, compare_to):
    """Exclude tables this project doesn't own from autogenerate/check.

    Google ADK's DatabaseSessionService (tech-stack.md's ADK session/state
    backing) creates its own tables (`sessions`, `events`, `app_states`,
    `user_states`, `adk_internal_metadata`) directly against this same
    Postgres database, outside Alembic entirely -- they exist in every real
    deployment's DB but are never in `Base.metadata`. Without this filter,
    every one of them would be reported as a false "remove_table" diff on
    every single comparison (spec 021 SC-003's "zero false positives"),
    since Neon branches copy `staging`'s already-ADK-populated schema.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True
