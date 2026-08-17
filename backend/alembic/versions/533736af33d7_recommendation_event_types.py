"""recommendation event types

Revision ID: 533736af33d7
Revises: 21a9819b3e22
Create Date: 2026-08-16 19:55:22.900542

Adds three `assessment_event_type` enum labels for the Recommendation
Agent (spec 002): `recommendation_report_generated`,
`weak_area_flagged`, `next_step_suggested` -- see FR-008 and
data-model.md's AssessmentEventType additions.

Also relaxes `assessment_events.topic_id` to nullable:
`recommendation_report_generated` summarizes a whole report rather than
a single topic, so it has no single `topic_id` to set. Every other
event type (existing and new) still always sets a real `topic_id` --
this is additive/backward-compatible, not a behavior change for them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "533736af33d7"
down_revision: str | Sequence[str] | None = "21a9819b3e22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_EVENT_TYPES = (
    "recommendation_report_generated",
    "weak_area_flagged",
    "next_step_suggested",
)


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- no
    # AUTOCOMMIT block needed here since nothing in this migration uses
    # the new values.
    for event_type in _NEW_EVENT_TYPES:
        op.execute(f"ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS '{event_type}'")

    op.alter_column("assessment_events", "topic_id", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Reverting topic_id to NOT NULL will fail if any
    # recommendation_report_generated row (topic_id IS NULL) exists --
    # such rows must be deleted first in that case.
    op.alter_column("assessment_events", "topic_id", existing_type=sa.String(), nullable=False)

    # Postgres has no DROP VALUE for enum labels; removing them safely
    # requires rebuilding the type (new type, migrate column, drop old
    # type). Not done here -- the three new labels are left in place on
    # downgrade.
