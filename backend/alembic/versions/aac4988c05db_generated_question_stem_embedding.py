"""generated question stem embedding

Revision ID: aac4988c05db
Revises: b17af4cb6d29
Create Date: 2026-10-12 00:00:00.000000

Bug-fix amendment, 2026-10-12 (specs/005-adaptive-quiz/research.md
§7-10, specs/001-domain-agnostic-core's matching Clarifications): adds
a nullable `stem_embedding vector(1024)` column to `generated_questions`
and `question_generation_cache`, replacing the near-duplicate check's
raw-text `difflib` comparison with embedding cosine similarity. No
backfill -- a `NULL` embedding is excluded from comparison rather than
treated as a match or non-match (both tables' rows age out of FR-008's
small lookback/pool windows regardless).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "aac4988c05db"
down_revision: str | Sequence[str] | None = "b17af4cb6d29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Matches src/models/generated_question.py's and
# src/models/question_generation_cache.py's own EMBEDDING_DIMENSION.
EMBEDDING_DIMENSION = 1024


def upgrade() -> None:
    """Upgrade schema."""
    # Already enabled by de54cd54219e (Milestone 9) -- idempotent guard,
    # not a re-introduction.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "generated_questions",
        sa.Column("stem_embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
    )
    op.add_column(
        "question_generation_cache",
        sa.Column("stem_embedding", Vector(EMBEDDING_DIMENSION), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("question_generation_cache", "stem_embedding")
    op.drop_column("generated_questions", "stem_embedding")
