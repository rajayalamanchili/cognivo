"""standards alignment schema

Revision ID: 9ad1c4c0ce38
Revises: 7a3145c13caf
Create Date: 2026-10-04 00:00:00.000000

Adds spec 038's standards-alignment schema (data-model.md): a new
`standards_tags` table tagging a graded topic with a real curriculum
standard (e.g. a Common Core Math code). Additive-only, no backfill --
an existing topic with no tags is correctly represented by having zero
rows here (FR-009).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9ad1c4c0ce38"
down_revision: str | Sequence[str] | None = "7a3145c13caf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "standards_tags",
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("framework", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subject_id", "topic_id"],
            ["topics.subject_id", "topics.topic_id"],
            name="fk_standards_tags_subject_id_topic_id",
        ),
        sa.PrimaryKeyConstraint("subject_id", "topic_id", "framework", "code"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("standards_tags")
