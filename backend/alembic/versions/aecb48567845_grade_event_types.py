"""grade event types

Revision ID: aecb48567845
Revises: 45b821042da5
Create Date: 2026-09-06 06:52:13.944733

Adds spec 017's `grade_assigned`, `grade_unlocked`, and
`placement_question_skipped` `assessment_event_type` labels
(FR-010/data-model.md): the audited events placement's starting-grade
assignment, the Sequencing Agent's grade-unlock check, and the skip
endpoint each write.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aecb48567845"
down_revision: str | Sequence[str] | None = "45b821042da5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- no
    # AUTOCOMMIT block needed here since nothing in this migration uses
    # the new values (same reasoning as c80b05244e1c).
    op.execute("ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'grade_assigned'")
    op.execute("ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'grade_unlocked'")
    op.execute(
        "ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'placement_question_skipped'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no DROP VALUE for enum labels; removing these three
    # safely would require rebuilding assessment_event_type (new type,
    # migrate column, drop old type). Not done here -- the labels are
    # left in place on downgrade, same precedent as c80b05244e1c.
