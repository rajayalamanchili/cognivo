"""guardian settings and roster listing

Revision ID: b9e68940cc10
Revises: d8e4b5a1f3c7
Create Date: 2026-10-06 00:00:00.000000

Spec 041 (guardian-public-ui-redesign), data-model.md: eleven new flat
columns across four existing tables, zero new tables.

- `real_guardian_accounts`: `name`, the six Settings Display/Notification
  preference toggles, and `password_changed_at` (FR-009/FR-011, and the
  session-invalidation mechanism research.md §6 adds -- stays `NULL`
  until the first real password change, not backfilled to `created_at`,
  so no existing session token is retroactively invalidated).
- `real_instructor_accounts`: `display_name` (FR-017) -- nullable, never
  collected at registration.
- `learner_profiles`: `practice_reminders_enabled` (FR-011) -- the one
  per-learner toggle.
- `classroom_rosters`: `is_listed` (FR-018) -- mutual exclusion with a
  closed `enrollment_mode` is an application-level invariant
  (`services/roster/enrollment.py`), not a DB constraint, same precedent
  as this table's existing `grade` validation.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9e68940cc10"
down_revision: str | Sequence[str] | None = "d8e4b5a1f3c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("real_guardian_accounts", sa.Column("name", sa.String(), nullable=True))
    op.add_column(
        "real_guardian_accounts",
        sa.Column("read_aloud_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "real_guardian_accounts",
        sa.Column("larger_text", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "real_guardian_accounts",
        sa.Column("reduce_motion", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "real_guardian_accounts",
        sa.Column("theme", sa.String(), nullable=False, server_default="system"),
    )
    op.add_column(
        "real_guardian_accounts",
        sa.Column(
            "quiz_finished_email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "real_guardian_accounts",
        sa.Column(
            "weekly_summary_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "real_guardian_accounts",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "real_instructor_accounts", sa.Column("display_name", sa.String(), nullable=True)
    )
    op.add_column(
        "learner_profiles",
        sa.Column(
            "practice_reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "classroom_rosters",
        sa.Column("is_listed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("classroom_rosters", "is_listed")
    op.drop_column("learner_profiles", "practice_reminders_enabled")
    op.drop_column("real_instructor_accounts", "display_name")
    op.drop_column("real_guardian_accounts", "password_changed_at")
    op.drop_column("real_guardian_accounts", "weekly_summary_enabled")
    op.drop_column("real_guardian_accounts", "quiz_finished_email_enabled")
    op.drop_column("real_guardian_accounts", "theme")
    op.drop_column("real_guardian_accounts", "reduce_motion")
    op.drop_column("real_guardian_accounts", "larger_text")
    op.drop_column("real_guardian_accounts", "read_aloud_default")
    op.drop_column("real_guardian_accounts", "name")
