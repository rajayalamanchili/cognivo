"""tutor agent

Revision ID: de54cd54219e
Revises: 8edc56919f60
Create Date: 2026-08-24 00:00:00.000000

Spec 012: enables the `pgvector` extension and adds
`content_passage_embeddings` (retrieval), `tutoring_sessions`, and
`tutor_exchanges` -- plus the `tutor_exchange_completed`
`assessment_event_type` label. See data-model.md for the full schema.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de54cd54219e"
down_revision: str | Sequence[str] | None = "8edc56919f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# voyage-3's output dimension (research.md §1) -- matches
# src/models/content_passage_embedding.py's EMBEDDING_DIMENSION.
EMBEDDING_DIMENSION = 1024

passage_field_enum = postgresql.ENUM(
    "skill_summary",
    "difficulty_easy",
    "difficulty_medium",
    "difficulty_hard",
    name="passage_field",
    create_type=False,
)
tutoring_session_status_enum = postgresql.ENUM(
    "active", "ended", name="tutoring_session_status", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    # `tutor-agent/` itself never touches Postgres (research.md §2) --
    # this extension is enabled once here, on the backend's own
    # database, for the `Vector` column type below.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    passage_field_enum.create(bind, checkfirst=True)
    tutoring_session_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "content_passage_embeddings",
        sa.Column("passage_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("field", passage_field_enum, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("content_version", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "topic_id"],
            ["topics.subject_id", "topics.topic_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("passage_id"),
        sa.UniqueConstraint(
            "subject_id",
            "topic_id",
            "field",
            "content_version",
            name="uq_content_passage_embeddings_subject_topic_field_version",
        ),
    )
    # HNSW index for `pgvector` cosine-similarity search (data-model.md),
    # scoped per-query to a subject_id via passage_search.py's WHERE
    # clause, not by a separate index per subject.
    op.create_index(
        "ix_content_passage_embeddings_embedding_cosine",
        "content_passage_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "tutoring_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("status", tutoring_session_status_enum, nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["guardian_id"], ["real_guardian_accounts.guardian_id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    # Partial unique index, not a plain UniqueConstraint -- FR-014's "at
    # most one active session per learner per subject" only applies
    # while status = 'active'; an ended session must not block a new one
    # (research.md §8, data-model.md).
    op.create_index(
        "uq_tutoring_sessions_active_learner_subject",
        "tutoring_sessions",
        ["learner_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "tutor_exchanges",
        sa.Column("exchange_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "retrieved_passage_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("delegation_context", sa.JSON(), nullable=True),
        # Nullable timestamptz set on A2A stream failure/timeout --
        # distinguishes "died mid-stream" from "still streaming"
        # (/speckit-analyze finding H2, data-model.md). Never set
        # together with a non-null answer_text.
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["session_id"], ["tutoring_sessions.session_id"]),
        sa.PrimaryKeyConstraint("exchange_id"),
    )

    # ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # that later reads/writes that value, but adding the label itself is
    # safe inside Alembic's default transaction on Postgres 12+ -- no
    # AUTOCOMMIT block needed here since nothing in this migration uses
    # the new value (same reasoning as 8bdb11ba393a/a7b77bd7fea5).
    op.execute(
        "ALTER TYPE assessment_event_type ADD VALUE IF NOT EXISTS 'tutor_exchange_completed'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tutor_exchanges")

    op.drop_index("uq_tutoring_sessions_active_learner_subject", table_name="tutoring_sessions")
    op.drop_table("tutoring_sessions")

    op.drop_index(
        "ix_content_passage_embeddings_embedding_cosine",
        table_name="content_passage_embeddings",
    )
    op.drop_table("content_passage_embeddings")

    bind = op.get_bind()
    tutoring_session_status_enum.drop(bind, checkfirst=True)
    passage_field_enum.drop(bind, checkfirst=True)

    op.execute("DROP EXTENSION IF EXISTS vector")

    # Postgres has no DROP VALUE for enum labels; removing
    # 'tutor_exchange_completed' safely would require rebuilding
    # assessment_event_type (new type, migrate column, drop old type).
    # Not done here -- the label is left in place on downgrade, same
    # precedent as 8bdb11ba393a/5a723b34fc55.
