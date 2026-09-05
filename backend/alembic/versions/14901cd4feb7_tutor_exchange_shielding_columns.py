"""tutor exchange shielding columns

Revision ID: 14901cd4feb7
Revises: 8e384ff83a4c
Create Date: 2026-09-04 00:00:00.000000

Adds spec 016's `shielded`/`shielded_question_id` columns to
`tutor_exchanges` (FR-007, data-model.md), mirroring the existing
`grounded`/`retrieved_passage_ids` pair. Additive-only, no backfill --
every existing row predates this feature and is correctly represented
by `shielded = false, shielded_question_id = NULL`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "14901cd4feb7"
down_revision: str | Sequence[str] | None = "8e384ff83a4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tutor_exchanges",
        sa.Column("shielded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tutor_exchanges",
        sa.Column("shielded_question_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tutor_exchanges_shielded_question_id",
        "tutor_exchanges",
        "generated_questions",
        ["shielded_question_id"],
        ["question_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_tutor_exchanges_shielded_question_id", "tutor_exchanges", type_="foreignkey"
    )
    op.drop_column("tutor_exchanges", "shielded_question_id")
    op.drop_column("tutor_exchanges", "shielded")
