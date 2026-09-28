"""mastery state has been mastered column

Revision ID: 824e2c5a0678
Revises: 5033078cfc81
Create Date: 2026-09-27 22:39:30.508268

Adds `mastery_states.has_been_mastered` (spec 025 FR-011, PR #90
review): a sticky flag distinguishing a genuine decay/wrong-answer
recovery ("refreshed") from a topic reaching `mastered` for the very
first time -- `band` alone can't make that distinction since it's
derived at read time, never persisted as history (data-model.md).

Backfill: any row whose current `p_mastery`/`consecutive_mastered_
observations` already derive to `mastered` (mirrors
`models.enums.mastery_band_for`'s own threshold/confirmation-streak
logic) has obviously been mastered before now, so it's backfilled to
`true`; every other existing row defaults to `false`, which is correct
-- a row that isn't currently mastered has no persisted way to tell
whether it was mastered at some earlier point, and treating it as "not
yet mastered" is the conservative choice (a false "not yet" only
suppresses a `refreshed` acknowledgment once; a false "already mastered"
would fabricate one).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "824e2c5a0678"
down_revision: str | Sequence[str] | None = "5033078cfc81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MASTERY_CONFIRMATION_THRESHOLD = 2


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "mastery_states",
        sa.Column("has_been_mastered", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        f"""
        UPDATE mastery_states
        SET has_been_mastered = true
        WHERE p_mastery >= 0.7
          AND consecutive_mastered_observations >= {_MASTERY_CONFIRMATION_THRESHOLD}
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("mastery_states", "has_been_mastered")
