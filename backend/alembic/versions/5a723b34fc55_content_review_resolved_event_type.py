"""content review resolved event type

Revision ID: 5a723b34fc55
Revises: 0892d285dcd8
Create Date: 2026-08-23 00:00:00.000002

Adds spec 010's `content_review_resolved` `assessment_event_type` label
(FR-013): the audited event a content-review resolution
(reactivate/reject) records, capturing the resolving instructor and
the action taken.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a723b34fc55"
down_revision: str | Sequence[str] | None = "0892d285dcd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- no
    # AUTOCOMMIT block needed here since nothing in this migration uses
    # the new value (same reasoning as a7b77bd7fea5/533736af33d7).
    op.execute("ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'content_review_resolved'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enum labels; removing
    # 'content_review_resolved' safely would require rebuilding
    # assessment_event_type (new type, migrate column, drop old type).
    # Not done here -- the label is left in place on downgrade, same
    # precedent as a7b77bd7fea5/533736af33d7.
