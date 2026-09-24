"""timed practice quiz mode

Revision ID: 5033078cfc81
Revises: 1697587733ae
Create Date: 2026-09-23 00:00:00.000000

Spec 022 (Milestone 20) Foundational schema (data-model.md): adds
`quiz_sessions.time_limit_seconds` (nullable -- NULL means untimed,
unchanged default, FR-001/FR-009); creates `practice_sessions` (a new
table, only ever populated for timed practice, FR-008), reusing the
existing `quiz_session_status` enum type rather than duplicating it;
adds `generated_questions.practice_session_id` (nullable FK, parallel
to the existing `quiz_session_id`/`placement_session_id` columns); and
adds the `timed_session_ended` `assessment_event_type` label (FR-007,
research.md §3).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5033078cfc81"
down_revision: str | Sequence[str] | None = "1697587733ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

quiz_session_status_enum = postgresql.ENUM(
    "in_progress", "completed", "ended_early", name="quiz_session_status", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "quiz_sessions", sa.Column("time_limit_seconds", sa.Integer(), nullable=True)
    )

    op.create_table(
        "practice_sessions",
        sa.Column("practice_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False),
        sa.Column("status", quiz_session_status_enum, nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("practice_session_id"),
    )

    op.add_column(
        "generated_questions",
        sa.Column("practice_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_generated_questions_practice_session_id",
        "generated_questions",
        "practice_sessions",
        ["practice_session_id"],
        ["practice_session_id"],
    )

    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- same
    # precedent as c80b05244e1c/a7b77bd7fea5.
    op.execute("ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'timed_session_ended'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_generated_questions_practice_session_id", "generated_questions", type_="foreignkey"
    )
    op.drop_column("generated_questions", "practice_session_id")
    op.drop_table("practice_sessions")
    op.drop_column("quiz_sessions", "time_limit_seconds")
    # Postgres has no DROP VALUE for enum labels; removing
    # 'timed_session_ended' safely would require rebuilding
    # assessment_event_type (new type, migrate column, drop old type).
    # Not done here -- the label is left in place on downgrade, same
    # precedent as c80b05244e1c/a7b77bd7fea5/533736af33d7.
