"""misconception classified event type

Revision ID: c80b05244e1c
Revises: 6b009f130a24
Create Date: 2026-08-31 00:00:00.000000

Adds Milestone 11's `misconception_classified` `assessment_event_type`
label (spec 013 FR-008/data-model.md): the audited event the offline
classification job writes when a learner/topic pair's accumulated
free-text answers match a named misconception pattern with enough
evidence and confidence.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c80b05244e1c"
down_revision: str | Sequence[str] | None = "6b009f130a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- no
    # AUTOCOMMIT block needed here since nothing in this migration uses
    # the new value (same reasoning as a7b77bd7fea5/533736af33d7).
    op.execute("ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'misconception_classified'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enum labels; removing
    # 'misconception_classified' safely would require rebuilding
    # assessment_event_type (new type, migrate column, drop old type).
    # Not done here -- the label is left in place on downgrade, same
    # precedent as a7b77bd7fea5/533736af33d7.
