"""grade banded curriculum schema

Revision ID: 45b821042da5
Revises: 14901cd4feb7
Create Date: 2026-09-06 06:49:14.279515

Adds spec 017's grade-banding schema (data-model.md): a new
`grade_bands` existence table, nullable `topics.grade` (FK ->
`grade_bands`), nullable `generated_questions.grade` /
`generated_questions.placement_session_id`, and a new
`grade_progress` table. Additive-only, no backfill -- every
existing row predates this feature and is correctly represented by
`grade IS NULL` / no `grade_progress` row (FR-009).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "45b821042da5"
down_revision: str | Sequence[str] | None = "14901cd4feb7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "grade_bands",
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("subject_id", "grade"),
        sa.CheckConstraint("grade BETWEEN 1 AND 12", name="ck_grade_bands_grade_range"),
    )

    op.add_column("topics", sa.Column("grade", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_topics_subject_id_grade",
        "topics",
        "grade_bands",
        ["subject_id", "grade"],
        ["subject_id", "grade"],
    )

    op.add_column("generated_questions", sa.Column("grade", sa.Integer(), nullable=True))
    op.add_column(
        "generated_questions",
        sa.Column("placement_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "grade_progress",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("unlocked_grade", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("learner_id", "subject_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("grade_progress")
    op.drop_column("generated_questions", "placement_session_id")
    op.drop_column("generated_questions", "grade")
    op.drop_constraint("fk_topics_subject_id_grade", "topics", type_="foreignkey")
    op.drop_column("topics", "grade")
    op.drop_table("grade_bands")
