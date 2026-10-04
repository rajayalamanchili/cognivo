"""assessment_events activity index

Revision ID: 7a3145c13caf
Revises: cf781636cccd
Create Date: 2026-10-03 00:00:00.000000

PR #99 review: `activity_summary.py` (027-learner-ui-redesign FR-009)
and `recently_refreshed.py`'s dashboard "Refreshed!" lookup both filter
`assessment_events` on `(learner_id, subject_id, created_at)` (plus
`event_type`, low-cardinality), with no covering index -- the only
declared index on this table is the partial unique one on
`question_id`. Fine at demo scale; becomes a full-table scan per
dashboard load as the audit log grows.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a3145c13caf"
down_revision: str | Sequence[str] | None = "cf781636cccd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_assessment_events_learner_subject_created_at",
        "assessment_events",
        ["learner_id", "subject_id", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_assessment_events_learner_subject_created_at", table_name="assessment_events"
    )
