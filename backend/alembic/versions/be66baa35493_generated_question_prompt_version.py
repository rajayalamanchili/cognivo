"""generated question prompt version

Revision ID: be66baa35493
Revises: c80b05244e1c
Create Date: 2026-09-01 19:45:22.922601

Adds Milestone 12's `generation_prompt_version` column to
`generated_questions` (spec 014 FR-009/data-model.md): which
Assessment-Generation prompt version produced each row, matching the
existing `grading_logic_version`/`classifier_version` explainability
pattern. Nullable, no default, no backfill -- existing rows predate
this milestone and were never versioned to begin with, so `NULL` means
"not tracked," not a fabricated value.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "be66baa35493"
down_revision: str | Sequence[str] | None = "c80b05244e1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "generated_questions", sa.Column("generation_prompt_version", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("generated_questions", "generation_prompt_version")
