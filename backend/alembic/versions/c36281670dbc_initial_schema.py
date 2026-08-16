"""initial schema

Revision ID: c36281670dbc
Revises:
Create Date: 2026-08-15 21:33:19.893639

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c36281670dbc"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

difficulty_band = postgresql.ENUM(
    "easy", "medium", "hard", name="difficulty_band", create_type=False
)
question_type_enum = postgresql.ENUM(
    "multiple_choice", "numeric", name="question_type", create_type=False
)
validation_status_enum = postgresql.ENUM(
    "pending", "valid", "invalid", "flagged", name="validation_status", create_type=False
)
assessment_event_type_enum = postgresql.ENUM(
    "placement_question_shown",
    "answer_submitted",
    "mastery_updated",
    "next_topic_selected",
    "question_flagged",
    name="assessment_event_type",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    difficulty_band.create(bind, checkfirst=True)
    question_type_enum.create(bind, checkfirst=True)
    validation_status_enum.create(bind, checkfirst=True)
    assessment_event_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "subjects",
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("content_version", sa.String(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("subject_id"),
    )

    op.create_table(
        "demo_learner_profiles",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("learner_id"),
    )

    op.create_table(
        "topics",
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("is_entry_level", sa.Boolean(), nullable=False),
        sa.Column("skill_definition", sa.JSON(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("subject_id", "topic_id"),
        sa.UniqueConstraint("subject_id", "order_index", name="uq_topics_subject_order_index"),
    )

    op.create_table(
        "prerequisite_edges",
        sa.Column("edge_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("from_topic_id", sa.String(), nullable=False),
        sa.Column("to_topic_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subject_id", "from_topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "to_topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        sa.PrimaryKeyConstraint("edge_id"),
        sa.UniqueConstraint(
            "subject_id", "from_topic_id", "to_topic_id", name="uq_prerequisite_edges_triple"
        ),
    )

    op.create_table(
        "mastery_states",
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("p_mastery", sa.Float(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("update_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["learner_id"], ["demo_learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(
            ["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        sa.PrimaryKeyConstraint("learner_id", "subject_id", "topic_id"),
    )

    op.create_table(
        "generated_questions",
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("difficulty", difficulty_band, nullable=False),
        sa.Column("question_type", question_type_enum, nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("answer_key", sa.JSON(), nullable=False),
        sa.Column(
            "validation_status",
            validation_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("flagged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("flagged_reason", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["demo_learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["flagged_by"], ["demo_learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(
            ["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        sa.PrimaryKeyConstraint("question_id"),
    )

    op.create_table(
        "assessment_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", assessment_event_type_enum, nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["learner_id"], ["demo_learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["question_id"], ["generated_questions.question_id"]),
        sa.ForeignKeyConstraint(
            ["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("assessment_events")
    op.drop_table("generated_questions")
    op.drop_table("mastery_states")
    op.drop_table("prerequisite_edges")
    op.drop_table("topics")
    op.drop_table("demo_learner_profiles")
    op.drop_table("subjects")

    bind = op.get_bind()
    assessment_event_type_enum.drop(bind, checkfirst=True)
    validation_status_enum.drop(bind, checkfirst=True)
    question_type_enum.drop(bind, checkfirst=True)
    difficulty_band.drop(bind, checkfirst=True)
