"""classroom roster instructor_id not fk

Revision ID: 7e686faa5e6d
Revises: 5a723b34fc55
Create Date: 2026-08-23 00:00:00.000003

Drops `classroom_rosters.instructor_id`'s foreign key to
`real_instructor_accounts` (`/speckit-clarify` with the user, spec 010
Phase 7): the seeded demo instructor now gets a real, navigable session
(`DemoInstructorProfile`, a table structurally separate from
`real_instructor_accounts` by design -- see `demo_instructor_profile.py`'s
own docstring), so a roster the demo instructor creates can't satisfy a
FK pointing at only one of the two tables an instructor identity might
live in. Matches the precedent `RetentionRecord.account_id` and
`DeletionRequest.target_id` already set for this exact "could
legitimately point at more than one table" shape (data-model.md) --
enforced at the application layer (`current_instructor`, which only
ever returns a real or demo instructor's own, already-authenticated id)
rather than a DB constraint.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e686faa5e6d"
down_revision: str | Sequence[str] | None = "5a723b34fc55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "classroom_rosters_instructor_id_fkey", "classroom_rosters", type_="foreignkey"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.create_foreign_key(
        "classroom_rosters_instructor_id_fkey",
        "classroom_rosters",
        "real_instructor_accounts",
        ["instructor_id"],
        ["instructor_id"],
    )
