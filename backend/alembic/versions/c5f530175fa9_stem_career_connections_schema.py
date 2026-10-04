"""stem career connections schema

Revision ID: c5f530175fa9
Revises: 9ad1c4c0ce38
Create Date: 2026-10-04 00:00:00.000000

Adds `topics.career_connection` (spec 039 FR-001/FR-002, data-model.md):
a nullable JSON column, zero or one per topic, mirroring `image_asset`'s
existing shape exactly -- no new table, unlike Standards Alignment's
`StandardsTag`.

Adds `learner_profiles.career_connections_enabled` (spec 039 FR-005/
FR-008): a non-nullable boolean, `server_default=true` so every existing
row (the seeded demo learner, every already-created real learner) picks
up the default-on preference with no separate backfill step, mirroring
`824e2c5a0678_mastery_state_has_been_mastered_column.py`'s add-column
shape.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5f530175fa9"
down_revision: str | Sequence[str] | None = "9ad1c4c0ce38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("topics", sa.Column("career_connection", sa.JSON(), nullable=True))
    op.add_column(
        "learner_profiles",
        sa.Column(
            "career_connections_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("learner_profiles", "career_connections_enabled")
    op.drop_column("topics", "career_connection")
