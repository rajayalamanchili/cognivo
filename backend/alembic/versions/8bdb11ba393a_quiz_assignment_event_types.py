"""quiz assignment event types

Revision ID: 8bdb11ba393a
Revises: 7e686faa5e6d
Create Date: 2026-08-23 14:41:04.876527

Adds spec 011's `quiz_assignment_created`/`quiz_assignment_cancelled`
`assessment_event_type` labels (FR-015): one event per targeted learner,
written on assignment creation and on cancellation.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8bdb11ba393a"
down_revision: str | Sequence[str] | None = "7e686faa5e6d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- no
    # AUTOCOMMIT block needed here since nothing in this migration uses
    # the new value (same reasoning as 5a723b34fc55/a7b77bd7fea5).
    op.execute("ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'quiz_assignment_created'")
    op.execute(
        "ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'quiz_assignment_cancelled'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enum labels; removing these two
    # labels safely would require rebuilding assessment_event_type (new
    # type, migrate column, drop old type). Not done here -- the labels
    # are left in place on downgrade, same precedent as 5a723b34fc55.
