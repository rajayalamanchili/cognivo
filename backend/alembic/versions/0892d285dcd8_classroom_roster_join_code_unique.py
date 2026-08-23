"""classroom roster join_code unique

Revision ID: 0892d285dcd8
Revises: 767f85894aaf
Create Date: 2026-08-23 00:00:00.000001

`POST /api/rosters/join` (User Story 2) looks up a `ClassroomRoster` by
`join_code` alone (its request body has no `roster_id` field) -- that
lookup is only well-defined if the code is unique across every roster,
`closed` included (data-model.md's Correction: a `closed` roster is
generated a code too, just kept out of the create/PATCH API response).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0892d285dcd8"
down_revision: str | Sequence[str] | None = "767f85894aaf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_classroom_rosters_join_code", "classroom_rosters", ["join_code"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_classroom_rosters_join_code", "classroom_rosters", type_="unique")
