"""Regression coverage for the `alembic check` CI gate (spec 021 SC-001/
SC-002), exercising the same public comparison API `alembic check` wraps
internally (`compare_metadata`) rather than shelling out to the CLI --
see specs/021-schema-drift-ci-check/research.md §4 for why.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Column, Integer, MetaData, Table, text

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


def test_ignores_tables_not_owned_by_our_models(_schema_engine):
    # Simulates Google ADK's DatabaseSessionService tables (sessions,
    # events, app_states, user_states, adk_internal_metadata) -- created
    # directly against this same DB, outside Alembic entirely. Without
    # src/schema_comparison.py's include_object filter, a table like
    # this would show as a false "remove_table" diff on every PR.
    with _schema_engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE schema_drift_test_unowned_table (id integer)")
        )
    try:
        diffs = _diffs(_schema_engine, Base.metadata)
        removed_tables = [diff[1].name for diff in diffs if diff[0] == "remove_table"]
        assert "schema_drift_test_unowned_table" not in removed_tables
    finally:
        with _schema_engine.begin() as connection:
            connection.execute(text("DROP TABLE schema_drift_test_unowned_table"))


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
