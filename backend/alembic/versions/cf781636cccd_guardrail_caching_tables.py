"""guardrail caching tables

Revision ID: cf781636cccd
Revises: 824e2c5a0678
Create Date: 2026-09-30 11:26:06.238168

Spec 026 (data-model.md §1/§2/§3): `moderation_cache` (an exact-signature
cache of the pre-grading moderation guardrail's allow/block verdict,
FR-001/FR-003/FR-005) and `shielding_classification_cache` (an
exact-signature cache of the Tutor Agent's shielding-match classifier
verdict, FR-002/FR-003/FR-004/FR-005), plus two new counter columns on
`tutor_exchanges` (`shielding_checks_total`/`shielding_checks_from_cache`,
FR-009) since one exchange can span several independent shielding
checks. No `pgvector` needed here -- unlike spec 015's grading cache,
both new tables match on a plain hashed-text signature, not embedding
similarity (research.md §1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cf781636cccd"
down_revision: str | Sequence[str] | None = "824e2c5a0678"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "moderation_cache",
        sa.Column("cache_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text_signature", sa.Text(), nullable=False),
        sa.Column("moderation_instruction_version", sa.String(), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("cache_entry_id"),
    )
    op.create_index(
        "ix_moderation_cache_lookup",
        "moderation_cache",
        ["text_signature", "moderation_instruction_version"],
    )

    op.create_table(
        "shielding_classification_cache",
        sa.Column("cache_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pair_signature", sa.Text(), nullable=False),
        sa.Column(
            "shielding_classification_instruction_version", sa.String(), nullable=False
        ),
        sa.Column("matches", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("last_served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("cache_entry_id"),
    )
    op.create_index(
        "ix_shielding_classification_cache_lookup",
        "shielding_classification_cache",
        ["pair_signature", "shielding_classification_instruction_version"],
    )

    op.add_column(
        "tutor_exchanges",
        sa.Column("shielding_checks_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tutor_exchanges",
        sa.Column(
            "shielding_checks_from_cache", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tutor_exchanges", "shielding_checks_from_cache")
    op.drop_column("tutor_exchanges", "shielding_checks_total")

    op.drop_index(
        "ix_shielding_classification_cache_lookup", table_name="shielding_classification_cache"
    )
    op.drop_table("shielding_classification_cache")

    op.drop_index("ix_moderation_cache_lookup", table_name="moderation_cache")
    op.drop_table("moderation_cache")
