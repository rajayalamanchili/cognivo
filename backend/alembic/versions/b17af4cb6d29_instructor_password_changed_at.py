"""instructor password_changed_at

Revision ID: b17af4cb6d29
Revises: 6471826f56d9
Create Date: 2026-10-08 23:05:00.000000

Spec 043 (Claude Code Review finding on PR #111): one new nullable
column on `real_instructor_accounts`, mirroring `real_guardian_
accounts.password_changed_at` exactly -- no server default, stays
`NULL` until the first real password change via `POST /api/auth/
instructor/change-password`, so no existing session token is
retroactively invalidated when this migration runs.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b17af4cb6d29"
down_revision: str | Sequence[str] | None = "6471826f56d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "real_instructor_accounts",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("real_instructor_accounts", "password_changed_at")
