"""multimodal question stimuli

Revision ID: 6b009f130a24
Revises: de54cd54219e
Create Date: 2026-08-30 00:00:00.000000

Adds spec 003's per-topic image asset support: a nullable
`image_asset` JSON column on `topics`, and nullable `image_url`/
`image_alt_text` Text columns on `generated_questions`, snapshotted at
question-generation time. See data-model.md for the full schema. No
backfill -- existing rows default to `NULL` (unchanged, text-only
behavior).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b009f130a24"
down_revision: str | Sequence[str] | None = "de54cd54219e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("topics", sa.Column("image_asset", sa.JSON(), nullable=True))
    op.add_column("generated_questions", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column("generated_questions", sa.Column("image_alt_text", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("generated_questions", "image_alt_text")
    op.drop_column("generated_questions", "image_url")
    op.drop_column("topics", "image_asset")
