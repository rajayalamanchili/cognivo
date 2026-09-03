"""semantic caching tables

Revision ID: 8e384ff83a4c
Revises: be66baa35493
Create Date: 2026-09-02 06:15:17.888414

Milestone 13 (spec 015, data-model.md §1/§2): `question_generation_cache`
(a rotating pool of up to 5 previously-validated question-generation
results per (subject_id, topic_id, difficulty, content_version,
generation_prompt_version), FR-001/FR-012) and `grading_response_cache`
(a `pgvector`-matched cache of free-text grading results, scoped by a
content-hash `question_signature` since `GeneratedQuestion` rows are
per-learner and can't be matched by `question_id` across learners,
FR-002/FR-003/FR-004). The `vector` extension is already enabled
(`de54cd54219e`'s Tutor Agent migration) -- not re-enabled here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e384ff83a4c"
down_revision: str | Sequence[str] | None = "be66baa35493"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# voyage-3's output dimension -- matches
# src/models/content_passage_embedding.py's EMBEDDING_DIMENSION.
EMBEDDING_DIMENSION = 1024

difficulty_band_enum = postgresql.ENUM(
    "easy", "medium", "hard", name="difficulty_band", create_type=False
)
question_type_enum = postgresql.ENUM(
    "multiple_choice", "numeric", "free_text", name="question_type", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "question_generation_cache",
        sa.Column("cache_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("difficulty", difficulty_band_enum, nullable=False),
        sa.Column("content_version", sa.String(), nullable=False),
        sa.Column("generation_prompt_version", sa.String(), nullable=False),
        sa.Column("question_type", question_type_enum, nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("answer_key", sa.JSON(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_alt_text", sa.Text(), nullable=True),
        sa.Column("question_signature", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        sa.PrimaryKeyConstraint("cache_entry_id"),
    )
    op.create_index(
        "ix_question_generation_cache_lookup",
        "question_generation_cache",
        [
            "subject_id",
            "topic_id",
            "difficulty",
            "content_version",
            "generation_prompt_version",
            "created_at",
        ],
    )
    op.create_index(
        "ix_question_generation_cache_question_signature",
        "question_generation_cache",
        ["question_signature"],
    )

    op.create_table(
        "grading_response_cache",
        sa.Column("cache_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_signature", sa.Text(), nullable=False),
        sa.Column("answer_embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("grading_logic_version", sa.String(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("graduated_score", sa.Float(), nullable=False),
        sa.Column("criteria_met", sa.JSON(), nullable=False),
        sa.Column("criteria_missed", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("cache_entry_id"),
    )
    op.create_index(
        "ix_grading_response_cache_lookup",
        "grading_response_cache",
        ["question_signature", "grading_logic_version"],
    )
    # HNSW index for pgvector cosine-similarity search, same pattern as
    # `content_passage_embeddings` (de54cd54219e).
    op.create_index(
        "ix_grading_response_cache_embedding_cosine",
        "grading_response_cache",
        ["answer_embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"answer_embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_grading_response_cache_embedding_cosine", table_name="grading_response_cache")
    op.drop_index("ix_grading_response_cache_lookup", table_name="grading_response_cache")
    op.drop_table("grading_response_cache")
    op.drop_index(
        "ix_question_generation_cache_question_signature", table_name="question_generation_cache"
    )
    op.drop_index("ix_question_generation_cache_lookup", table_name="question_generation_cache")
    op.drop_table("question_generation_cache")
