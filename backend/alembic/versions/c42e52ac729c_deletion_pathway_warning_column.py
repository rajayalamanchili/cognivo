"""deletion pathway warning column

Revision ID: c42e52ac729c
Revises: d28eac600969
Create Date: 2026-09-21 07:28:29.105025

Adds spec 020's `retention_records.inactivity_warning_sent_at` column
(FR-011): set by the inactivity sweep 7 days before an account becomes
eligible for FR-010's auto-deletion, so the owning guardian/instructor
sees an in-app warning before it happens. Additive-only, no backfill --
every existing row defaults to `NULL`, meaning "not currently warned",
which is correct for every row that predates this feature.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c42e52ac729c"
down_revision: str | Sequence[str] | None = "d28eac600969"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "retention_records",
        sa.Column("inactivity_warning_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("retention_records", "inactivity_warning_sent_at")
