"""Regression coverage for the `alembic check` CI gate (spec 021 SC-001/
SC-002), exercising the same public comparison API `alembic check` wraps
internally (`compare_metadata`) rather than shelling out to the CLI --
see specs/021-schema-drift-ci-check/research.md §4 for why.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Column, Integer, MetaData, Table, inspect, text

from src.models import Base
from src.schema_comparison import include_object


def _diffs(engine, metadata):
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"include_object": include_object}
        )
        return compare_metadata(context, metadata)


def test_no_drift_against_current_models(_schema_engine):
    assert _diffs(_schema_engine, Base.metadata) == []


def test_detects_missing_migration_for_a_new_table(_schema_engine):
    drifted = MetaData()
    Table(
        "schema_drift_test_new_table",
        drifted,
        Column("id", Integer, primary_key=True),
    )
    diffs = _diffs(_schema_engine, drifted)
    added_tables = [diff[1].name for diff in diffs if diff[0] == "add_table"]
    assert "schema_drift_test_new_table" in added_tables


def test_ignores_only_known_externally_owned_tables(_schema_engine):
    # `sessions` stands in for Google ADK's DatabaseSessionService tables
    # -- created directly against this same DB, outside Alembic entirely.
    # Without src/schema_comparison.py's include_object filter, a table
    # like this would show as a false "remove_table" diff on every PR.
    # If it already exists (a real one, from real ADK usage against this
    # shared dev DB), leave it alone entirely -- never create or drop a
    # table that might be live app state.
    already_exists = inspect(_schema_engine).has_table("sessions")
    if not already_exists:
        with _schema_engine.begin() as connection:
            connection.execute(text("CREATE TABLE sessions (id integer)"))
    try:
        diffs = _diffs(_schema_engine, Base.metadata)
        removed_tables = [diff[1].name for diff in diffs if diff[0] == "remove_table"]
        assert "sessions" not in removed_tables
    finally:
        if not already_exists:
            with _schema_engine.begin() as connection:
                connection.execute(text("DROP TABLE sessions"))


def test_still_flags_genuinely_unexpected_tables_as_drift(_schema_engine):
    # The allowlist above must stay narrow: a table this project actually
    # owns being dropped from a model with no matching migration is
    # exactly the drift FR-001 exists to catch, and must not be silently
    # swallowed by the same filter that excuses ADK's own tables.
    with _schema_engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE schema_drift_test_genuinely_unexpected (id integer)")
        )
    try:
        diffs = _diffs(_schema_engine, Base.metadata)
        removed_tables = [diff[1].name for diff in diffs if diff[0] == "remove_table"]
        assert "schema_drift_test_genuinely_unexpected" in removed_tables
    finally:
        with _schema_engine.begin() as connection:
            connection.execute(text("DROP TABLE schema_drift_test_genuinely_unexpected"))


def test_detects_incomplete_migration_for_a_changed_column(_schema_engine):
    # `subjects` has no outgoing foreign keys, so it can be copied into a
    # standalone MetaData without also having to carry its referenced
    # tables along for to_metadata()'s FK resolution to succeed.
    drifted = MetaData()
    subjects_table = Base.metadata.tables["subjects"].to_metadata(drifted)
    subjects_table.append_column(Column("schema_drift_test_column", Integer))
    diffs = _diffs(_schema_engine, drifted)
    added_columns = [
        diff[3].name
        for diff in diffs
        if diff[0] == "add_column" and diff[2] == "subjects"
    ]
    assert "schema_drift_test_column" in added_columns
