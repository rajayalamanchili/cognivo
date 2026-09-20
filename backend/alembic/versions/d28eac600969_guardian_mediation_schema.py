"""guardian mediation schema

Revision ID: d28eac600969
Revises: 4ec9d9516a47
Create Date: 2026-09-20 08:09:21.237912

Adds spec 019's guardian-mediation schema: a new
`quiz_assignment_targets.guardian_viewed_at` column (FR-007, backs the
opt-in-nudges tier's in-app indicator) and a
`guardian_mediation_applied` `assessment_event_type` label (FR-012).
Additive-only, no backfill -- every existing row defaults to
`guardian_viewed_at = NULL` ("not yet viewed"), which is correct for
rows that predate this column. `MediationTier` (co_present/check_in/
opt_in_nudges/independent) is never persisted as a database enum --
data-model.md's "Never persisted as a column" note -- so there is no
corresponding Postgres type to create here.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d28eac600969"
down_revision: str | Sequence[str] | None = "4ec9d9516a47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "quiz_assignment_targets",
        sa.Column("guardian_viewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- same
    # technique as 4ec9d9516a47/aecb48567845.
    op.execute(
        "ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'guardian_mediation_applied'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("quiz_assignment_targets", "guardian_viewed_at")

    # Postgres has no DROP VALUE for enum labels; removing
    # 'guardian_mediation_applied' safely would require rebuilding the
    # type (new type, migrate column, drop old type). Not done here --
    # the label is left in place on downgrade, same precedent as every
    # prior enum-label migration in this project.
