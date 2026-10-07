"""guardian login lockout

Revision ID: b9344ef08c67
Revises: b9e68940cc10
Create Date: 2026-10-07 00:00:00.000000

Claude Code Review finding on PR #109: neither `/login` nor
`/change-password`'s `current_password` check had any throttle, so a
stolen session (or a public login form) could brute-force a guardian's
password with no limit. Two new columns on `real_guardian_accounts`
(`services/auth/lockout.py`'s state) -- `failed_login_attempts` defaults
to 0 so every existing row starts unlocked; `locked_until` stays `NULL`
until the first lockout, same precedent as this table's own
`password_changed_at`.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9344ef08c67"
down_revision: str | Sequence[str] | None = "b9e68940cc10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "real_guardian_accounts",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "real_guardian_accounts",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("real_guardian_accounts", "locked_until")
    op.drop_column("real_guardian_accounts", "failed_login_attempts")
