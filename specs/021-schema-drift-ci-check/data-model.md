# Phase 1 Data Model: Schema-Drift Detection CI Check

**Feature**: `031-schema-drift-ci-check` | **Date**: 2026-09-22

This feature adds no new database tables, columns, or migrations of its
own -- it's a CI gate over the *existing* model/migration relationship,
not a feature with its own persisted data (spec.md has no Key Entities
section for the same reason; per template instructions that section is
omitted rather than filled with "N/A").

The two things this feature does operate over are both already-existing
code-level artifacts, made concrete here for the implementation phase:

## 1. SQLAlchemy models (the "intended" schema)

`backend/src/models/` (aggregated as `Base.metadata` via
`backend/src/models/__init__.py`) is the source of truth this check
measures drift *against*. No changes to this directory are in scope --
the check observes it, it doesn't modify it.

## 2. Alembic migration history (the "actual" schema)

`backend/alembic/versions/` is the source of truth for what a real
deployment's database actually looks like once fully migrated
(`alembic upgrade head`). `backend/alembic/env.py` already binds
`target_metadata = Base.metadata` for both online/offline modes -- the
one piece of wiring `alembic check` depends on already exists and needs
no change.

No new migration is part of this feature. (If a future PR's own model
change needs a migration, that's an instance of the exact condition
this check now gates -- not something this feature's own implementation
should ever trigger, since it touches no models.)
