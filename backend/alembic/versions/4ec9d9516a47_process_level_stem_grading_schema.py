"""process level stem grading schema

Revision ID: 4ec9d9516a47
Revises: aecb48567845
Create Date: 2026-09-17 00:00:00.000000

Adds spec 018's process-level (step-by-step) STEM grading schema: a new
`topics.step_grading_enabled` column (FR-001), a `multi_step`
`question_type` label, and a `step_count_mismatch_rejected`
`assessment_event_type` label (FR-012). Additive-only, no backfill --
every existing topic defaults to `step_grading_enabled = false`, which
is exactly today's behavior (data-model.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4ec9d9516a47"
down_revision: str | Sequence[str] | None = "aecb48567845"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "topics",
        sa.Column("step_grading_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- same
    # technique as 407938ba90fc/aecb48567845.
    op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'multi_step'")
    op.execute(
        "ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'step_count_mismatch_rejected'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("topics", "step_grading_enabled")

    # Postgres has no DROP VALUE for enum labels; removing 'multi_step'/
    # 'step_count_mismatch_rejected' safely would require rebuilding
    # each type (new type, migrate column, drop old type). Not done
    # here -- the labels are left in place on downgrade, same precedent
    # as every prior enum-label migration in this project.
