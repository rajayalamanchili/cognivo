"""instructor preferences and defaults

Revision ID: 6471826f56d9
Revises: b9344ef08c67
Create Date: 2026-10-07 22:04:37.732364

Spec 043: eight new columns on `real_instructor_accounts`, mirroring
`real_guardian_accounts`' own `theme`/`larger_text`/`reduce_motion` and
`failed_login_attempts`/`locked_until` columns exactly, plus three new
ones (`notifications_enabled`, `default_enrollment_mode`,
`default_due_date_offset_days`). `default_enrollment_mode` reuses the
existing `enrollment_mode` Postgres enum type (create_type=False) --
no new enum. All eight carry a server default, so every existing row
stays valid with no backfill.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6471826f56d9"
down_revision: str | Sequence[str] | None = "b9344ef08c67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

enrollment_mode_enum = postgresql.ENUM("open", "closed", name="enrollment_mode", create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "real_instructor_accounts",
        sa.Column("theme", sa.String(), nullable=False, server_default="system"),
    )
    op.add_column(
        "real_instructor_accounts",
        sa.Column("larger_text", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "real_instructor_accounts",
        sa.Column("reduce_motion", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "real_instructor_accounts",
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "real_instructor_accounts",
        sa.Column("default_enrollment_mode", enrollment_mode_enum, nullable=False, server_default="open"),
    )
    op.add_column(
        "real_instructor_accounts",
        sa.Column("default_due_date_offset_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "real_instructor_accounts",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "real_instructor_accounts",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("real_instructor_accounts", "locked_until")
    op.drop_column("real_instructor_accounts", "failed_login_attempts")
    op.drop_column("real_instructor_accounts", "default_due_date_offset_days")
    op.drop_column("real_instructor_accounts", "default_enrollment_mode")
    op.drop_column("real_instructor_accounts", "notifications_enabled")
    op.drop_column("real_instructor_accounts", "reduce_motion")
    op.drop_column("real_instructor_accounts", "larger_text")
    op.drop_column("real_instructor_accounts", "theme")
