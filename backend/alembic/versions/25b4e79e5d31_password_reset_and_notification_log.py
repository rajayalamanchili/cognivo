"""password reset and notification log

Revision ID: 25b4e79e5d31
Revises: aac4988c05db
Create Date: 2026-10-12 00:00:00.000000

spec 045 data-model.md: two new tables, `password_reset_tokens` and
`notification_log_entries`. `account_type` on both reuses the existing
`authorized_by_type` enum rather than adding a new one (research.md
§2/§4); `notification_type`/`notification_status` are new.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "25b4e79e5d31"
down_revision: str | Sequence[str] | None = "aac4988c05db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

authorized_by_type_enum = postgresql.ENUM(
    "guardian", "instructor", name="authorized_by_type", create_type=False
)
notification_type_enum = postgresql.ENUM(
    "registration",
    "password_reset",
    "deletion_request_confirmation",
    name="notification_type",
    create_type=False,
)
notification_status_enum = postgresql.ENUM(
    "sent", "failed", name="notification_status", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    notification_type_enum.create(bind, checkfirst=True)
    notification_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "password_reset_tokens",
        sa.Column("reset_token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_type", authorized_by_type_enum, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("reset_token_id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "uq_password_reset_tokens_pending_account",
        "password_reset_tokens",
        ["account_type", "account_id"],
        unique=True,
        postgresql_where="used_at IS NULL",
    )

    op.create_table(
        "notification_log_entries",
        sa.Column("notification_log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", notification_type_enum, nullable=False),
        sa.Column("account_type", authorized_by_type_enum, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", notification_status_enum, nullable=False),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("notification_log_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("notification_log_entries")
    op.drop_index("uq_password_reset_tokens_pending_account", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    notification_status_enum.drop(op.get_bind(), checkfirst=True)
    notification_type_enum.drop(op.get_bind(), checkfirst=True)
