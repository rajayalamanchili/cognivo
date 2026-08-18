"""quiz sessions

Revision ID: a7b77bd7fea5
Revises: 533736af33d7
Create Date: 2026-08-18 06:29:52.932575

Adds spec 005's `QuizSession` entity: a new `quiz_sessions` table, a
nullable `quiz_session_id` FK column on `generated_questions` so a
quiz's questions can be grouped, and one new `assessment_event_type`
label (`quiz_difficulty_adjusted`) for FR-009's in-quiz
difficulty-decision logging. See data-model.md for the full schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b77bd7fea5"
down_revision: str | Sequence[str] | None = "533736af33d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

quiz_session_status_enum = postgresql.ENUM(
    "in_progress", "completed", "ended_early", name="quiz_session_status", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    quiz_session_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "quiz_sessions",
        sa.Column("quiz_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_ids", sa.JSON(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            quiz_session_status_enum,
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["demo_learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("quiz_session_id"),
    )

    op.add_column(
        "generated_questions",
        sa.Column("quiz_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_generated_questions_quiz_session_id",
        "generated_questions",
        "quiz_sessions",
        ["quiz_session_id"],
        ["quiz_session_id"],
    )

    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- no
    # AUTOCOMMIT block needed here since nothing in this migration uses
    # the new value (same reasoning as 533736af33d7).
    op.execute(
        "ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'quiz_difficulty_adjusted'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_generated_questions_quiz_session_id", "generated_questions", type_="foreignkey"
    )
    op.drop_column("generated_questions", "quiz_session_id")
    op.drop_table("quiz_sessions")

    bind = op.get_bind()
    quiz_session_status_enum.drop(bind, checkfirst=True)

    # Postgres has no DROP VALUE for enum labels; removing
    # 'quiz_difficulty_adjusted' safely would require rebuilding
    # assessment_event_type (new type, migrate column, drop old type).
    # Not done here -- the label is left in place on downgrade, same
    # precedent as 533736af33d7.
