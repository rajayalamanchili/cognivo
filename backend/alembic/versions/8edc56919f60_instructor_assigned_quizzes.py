"""instructor assigned quizzes

Revision ID: 8edc56919f60
Revises: 8bdb11ba393a
Create Date: 2026-08-23 14:41:28.869544

Spec 011: creates `quiz_assignments` and `quiz_assignment_targets` --
a pure join layer on top of Milestone 7's `classroom_rosters`/
`learner_profiles` and Milestone 5's `quiz_sessions`, none of which are
modified here (data-model.md).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8edc56919f60"
down_revision: str | Sequence[str] | None = "8bdb11ba393a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "quiz_assignments",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("roster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_ids", sa.JSON(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["roster_id"], ["classroom_rosters.roster_id"]),
        sa.ForeignKeyConstraint(["instructor_id"], ["real_instructor_accounts.instructor_id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("assignment_id"),
    )

    op.create_table(
        "quiz_assignment_targets",
        sa.Column("assignment_target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quiz_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["assignment_id"], ["quiz_assignments.assignment_id"]),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["quiz_session_id"], ["quiz_sessions.quiz_session_id"]),
        sa.PrimaryKeyConstraint("assignment_target_id"),
        sa.UniqueConstraint(
            "assignment_id", "learner_id", name="uq_quiz_assignment_targets_assignment_learner"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("quiz_assignment_targets")
    op.drop_table("quiz_assignments")
