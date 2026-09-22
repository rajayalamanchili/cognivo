"""deletion requests pending unique index

Revision ID: 1697587733ae
Revises: c42e52ac729c
Create Date: 2026-09-22 09:58:00.000000

Adds a partial unique index on `deletion_requests(target_type,
target_id) WHERE completed_at IS NULL` (PR #79 review): the existing
check-then-insert guard in `deletion.py`'s `submit_deletion_request`
(and the equivalent guards in `inactivity.py`'s `sweep_inactive_accounts`
and `execute.py`'s `_queue_guardian_deletion`) isn't race-proof on its
own -- this constraint is the actual arbiter for a concurrent duplicate
submission, same pattern as `TutoringSession`'s active-session index.
No backfill needed: any pre-existing duplicate pending rows for the
same target would violate this, but none can exist today since every
current write path already serializes through the same check.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1697587733ae"
down_revision: str | Sequence[str] | None = "c42e52ac729c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_deletion_requests_pending_target",
        "deletion_requests",
        ["target_type", "target_id"],
        unique=True,
        postgresql_where="completed_at IS NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_deletion_requests_pending_target", table_name="deletion_requests")
