"""Regression coverage for the `alembic check` CI gate (spec 021 SC-001/
SC-002), exercising the same public comparison API `alembic check` wraps
internally (`compare_metadata`) rather than shelling out to the CLI --
see specs/021-schema-drift-ci-check/research.md §4 for why.
"""

import shutil
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.command import upgrade
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import Column, Integer, MetaData, Table, inspect, text

from src.models import Base
from src.schema_comparison import include_object

BACKEND_DIR = Path(__file__).resolve().parents[2]


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
    # IF NOT EXISTS/IF EXISTS: this table is entirely test-owned (never
    # real app data, unlike `sessions` above), so idempotent create/drop
    # is safe -- guards against a killed process (CI timeout, OOM)
    # leaving this behind between the CREATE and the finally's DROP,
    # which would otherwise fail the next run's CREATE with "already
    # exists" instead of testing anything (code-review finding).
    with _schema_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_drift_test_genuinely_unexpected (id integer)"
            )
        )
    try:
        diffs = _diffs(_schema_engine, Base.metadata)
        removed_tables = [diff[1].name for diff in diffs if diff[0] == "remove_table"]
        assert "schema_drift_test_genuinely_unexpected" in removed_tables
    finally:
        with _schema_engine.begin() as connection:
            connection.execute(
                text("DROP TABLE IF EXISTS schema_drift_test_genuinely_unexpected")
            )


def test_fr004_multiple_migration_heads_fail_before_check_runs(database_available, tmp_path):
    # FR-004: `backend-tests.yml`'s "Run migrations" step (`alembic
    # upgrade head`) must already fail on an ambiguous multi-head
    # history before the new `alembic check` step is ever reached
    # (research.md §2) -- previously verified only once, manually, via
    # a throwaway scratch check never committed anywhere (tasks.md
    # T005/code-review). This is that check, permanent and automated.
    #
    # Copies the real migration history into an isolated tmp_path
    # script location rather than writing scratch revisions into the
    # real backend/alembic/versions/ -- a crash mid-test can never
    # leave stray files in the actual migration history this way.
    versions_copy = tmp_path / "versions"
    shutil.copytree(BACKEND_DIR / "alembic" / "versions", versions_copy)

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("version_locations", str(versions_copy))
    cfg.set_main_option(
        "sqlalchemy.url", database_available.replace("postgresql:", "postgresql+psycopg:")
    )

    script = ScriptDirectory.from_config(cfg)
    current_head = script.get_current_head()
    script.generate_revision("fr004brancha", "scratch head A", head=current_head, splice=True)
    script.generate_revision("fr004branchb", "scratch head B", head=current_head, splice=True)

    with pytest.raises(CommandError, match="Multiple head revisions"):
        upgrade(cfg, "head")


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
