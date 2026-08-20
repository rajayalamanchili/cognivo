"""answer_submitted unique per question

Revision ID: e04658523ea2
Revises: 407938ba90fc
Create Date: 2026-08-20 10:00:00.000000

Adds a partial unique index enforcing at most one `answer_submitted`
`AssessmentEvent` per `question_id` (PR #18 review). `answer_question`'s
`_already_answered` check-then-act pattern isn't enough on its own to
close a concurrent double-submission race for free-text answers, where
the moderation + Grading Agent A2A calls widen the window between the
check and the write to several seconds -- this index makes the DB the
final arbiter, so one of two concurrent submissions for the same
question always loses at INSERT time instead of both committing a
second `MASTERY_UPDATED` event.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e04658523ea2"
down_revision: str | Sequence[str] | None = "407938ba90fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE UNIQUE INDEX ix_assessment_events_answer_submitted_question_id "
        "ON assessment_events (question_id) "
        "WHERE event_type = 'answer_submitted'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX ix_assessment_events_answer_submitted_question_id")
