"""classroom roster grade column

Revision ID: d8e4b5a1f3c7
Revises: c5f530175fa9
Create Date: 2026-10-04 00:00:00.000000

Adds `classroom_rosters.grade` (spec 040 FR-009, data-model.md): a
nullable integer, opt-in per roster mirroring `grade_bands`' own
opt-in-per-subject precedent -- every existing roster stays
unrestricted with no backfill needed. Enforced at creation time by
`services/roster/enrollment.py`'s `create_roster` against the chosen
subject's own `GradeBand` rows, not by this constraint alone (the
constraint only guards the 1-12 range, same shape as `grade_bands`'
own `ck_grade_bands_grade_range`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e4b5a1f3c7"
down_revision: str | Sequence[str] | None = "c5f530175fa9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("classroom_rosters", sa.Column("grade", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_classroom_rosters_grade_range",
        "classroom_rosters",
        "grade IS NULL OR grade BETWEEN 1 AND 12",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_classroom_rosters_grade_range", "classroom_rosters", type_="check")
    op.drop_column("classroom_rosters", "grade")
