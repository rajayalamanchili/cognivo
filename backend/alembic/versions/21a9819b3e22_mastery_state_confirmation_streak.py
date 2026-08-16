"""mastery state confirmation streak

Revision ID: 21a9819b3e22
Revises: c36281670dbc
Create Date: 2026-08-15 22:03:26.537252

Adds `MasteryState.consecutive_mastered_observations` -- the "mastered"
band now requires two consecutive >=0.7 BKT posteriors, not one, so a
single lucky guess (numeric questions' low p(G)=0.05 makes one correct
answer strong evidence on its own) can't spike a topic straight to
"mastered" and get it pulled from future selection (FR-006), defeating
SC-005's degenerate-answer-pattern guarantee. See
src/models/enums.py's MASTERY_CONFIRMATION_THRESHOLD.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "21a9819b3e22"
down_revision: str | Sequence[str] | None = "c36281670dbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "mastery_states",
        sa.Column(
            "consecutive_mastered_observations",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("mastery_states", "consecutive_mastered_observations")
