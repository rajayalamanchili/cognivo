"""instructor classroom

Revision ID: 767f85894aaf
Revises: e04658523ea2
Create Date: 2026-08-23 00:00:00.000000

Spec 010: creates the eight tables spec 009's data-model.md described as
forward-looking (research.md §3), and applies data-model.md's Correction
to spec 009's original proposal -- rather than a separate real-learner
table, `demo_learner_profiles` is renamed to `learner_profiles` and gains
nullable `guardian_id`/`retention_record_id` columns, preserving the five
existing hard FKs (`assessment_events`, `mastery_states`,
`generated_questions` x2, `quiz_sessions`) that already point at it.

Order: `real_guardian_accounts`/`real_instructor_accounts`/
`retention_records` first (no FK dependency on the renamed table yet);
then the rename + new columns; then `classroom_rosters`/`enrollments`/
`enrollment_requests`/`deletion_requests`/`demo_instructor_profiles`,
which do depend on the renamed table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "767f85894aaf"
down_revision: str | Sequence[str] | None = "e04658523ea2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

enrollment_mode_enum = postgresql.ENUM("open", "closed", name="enrollment_mode", create_type=False)
authorized_by_type_enum = postgresql.ENUM(
    "guardian", "instructor", name="authorized_by_type", create_type=False
)
enrollment_decision_enum = postgresql.ENUM(
    "approved", "declined", name="enrollment_decision", create_type=False
)
deletion_target_type_enum = postgresql.ENUM(
    "learner", "instructor", "guardian", name="deletion_target_type", create_type=False
)
retention_account_type_enum = postgresql.ENUM(
    "learner", "instructor", name="retention_account_type", create_type=False
)
retention_enrollment_status_enum = postgresql.ENUM(
    "active", "inactive", name="retention_enrollment_status", create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    enrollment_mode_enum.create(bind, checkfirst=True)
    authorized_by_type_enum.create(bind, checkfirst=True)
    enrollment_decision_enum.create(bind, checkfirst=True)
    deletion_target_type_enum.create(bind, checkfirst=True)
    retention_account_type_enum.create(bind, checkfirst=True)
    retention_enrollment_status_enum.create(bind, checkfirst=True)

    # --- No FK dependency on demo_learner_profiles/learner_profiles ---

    op.create_table(
        "real_guardian_accounts",
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("guardian_id"),
        sa.UniqueConstraint("email", name="uq_real_guardian_accounts_email"),
    )

    op.create_table(
        "real_instructor_accounts",
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("instructor_id"),
        sa.UniqueConstraint("email", name="uq_real_instructor_accounts_email"),
    )

    op.create_table(
        "retention_records",
        sa.Column("retention_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_type", retention_account_type_enum, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authorized_by_type", authorized_by_type_enum, nullable=False),
        sa.Column("authorized_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enrollment_status", retention_enrollment_status_enum, nullable=False),
        sa.Column("became_inactive_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("retention_record_id"),
    )

    # --- Rename + extend (data-model.md's Correction to spec 009) ---

    op.rename_table("demo_learner_profiles", "learner_profiles")
    op.add_column(
        "learner_profiles",
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "learner_profiles",
        sa.Column("retention_record_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_learner_profiles_guardian_id",
        "learner_profiles",
        "real_guardian_accounts",
        ["guardian_id"],
        ["guardian_id"],
    )
    op.create_foreign_key(
        "fk_learner_profiles_retention_record_id",
        "learner_profiles",
        "retention_records",
        ["retention_record_id"],
        ["retention_record_id"],
    )

    # --- Depend on learner_profiles/real_instructor_accounts existing ---

    op.create_table(
        "classroom_rosters",
        sa.Column("roster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("enrollment_mode", enrollment_mode_enum, nullable=False),
        sa.Column("join_code", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["instructor_id"], ["real_instructor_accounts.instructor_id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.subject_id"]),
        sa.PrimaryKeyConstraint("roster_id"),
    )

    op.create_table(
        "enrollments",
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("roster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "enrolled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("authorized_by_type", authorized_by_type_enum, nullable=False),
        sa.Column("authorized_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["roster_id"], ["classroom_rosters.roster_id"]),
        sa.PrimaryKeyConstraint("enrollment_id"),
        sa.UniqueConstraint("learner_id", "roster_id", name="uq_enrollments_learner_roster"),
    )

    op.create_table(
        "enrollment_requests",
        sa.Column("enrollment_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("roster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", enrollment_decision_enum, nullable=True),
        sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.learner_id"]),
        sa.ForeignKeyConstraint(["roster_id"], ["classroom_rosters.roster_id"]),
        sa.PrimaryKeyConstraint("enrollment_request_id"),
    )

    # --- No FK dependency on learner_profiles (deliberately, spec 009) ---

    op.create_table(
        "deletion_requests",
        sa.Column("deletion_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", deletion_target_type_enum, nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("deletion_request_id"),
    )

    op.create_table(
        "demo_instructor_profiles",
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("instructor_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("demo_instructor_profiles")
    op.drop_table("deletion_requests")
    op.drop_table("enrollment_requests")
    op.drop_table("enrollments")
    op.drop_table("classroom_rosters")

    op.drop_constraint(
        "fk_learner_profiles_retention_record_id", "learner_profiles", type_="foreignkey"
    )
    op.drop_constraint("fk_learner_profiles_guardian_id", "learner_profiles", type_="foreignkey")
    op.drop_column("learner_profiles", "retention_record_id")
    op.drop_column("learner_profiles", "guardian_id")
    op.rename_table("learner_profiles", "demo_learner_profiles")

    op.drop_table("retention_records")
    op.drop_table("real_instructor_accounts")
    op.drop_table("real_guardian_accounts")

    bind = op.get_bind()
    retention_enrollment_status_enum.drop(bind, checkfirst=True)
    retention_account_type_enum.drop(bind, checkfirst=True)
    deletion_target_type_enum.drop(bind, checkfirst=True)
    enrollment_decision_enum.drop(bind, checkfirst=True)
    authorized_by_type_enum.drop(bind, checkfirst=True)
    enrollment_mode_enum.drop(bind, checkfirst=True)
