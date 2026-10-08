import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, false, func, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import EnrollmentMode, enum_values


class RealInstructorAccount(Base):
    """An instructor's real, credential-holding account (spec 009, research.md
    §2). `email` is unique within this table only -- the same person may
    separately hold a `RealGuardianAccount` under the same email.

    `display_name` (spec 041 FR-017, data-model.md) is nullable at the DB
    level and never collected at registration -- `register_instructor` is
    unchanged. It's set only via `PATCH /api/auth/instructor/me`, required
    before `is_listed=True` can be set on any of this instructor's rosters
    (`services/roster/enrollment.py`), identically for a brand-new and a
    pre-existing account.
    """

    __tablename__ = "real_instructor_accounts"

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # spec 043: Settings-page fields, mirroring RealGuardianAccount's
    # identical theme/larger_text/reduce_motion columns exactly.
    theme: Mapped[str] = mapped_column(
        String, nullable=False, default="system", server_default="system"
    )
    larger_text: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    reduce_motion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Persisted only -- no code path ever reads this to send a
    # notification (spec 043 FR-008).
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    # Pre-fills the Rosters create-roster/assign-quiz forms client-side
    # only (spec 043 FR-009) -- never applied retroactively.
    default_enrollment_mode: Mapped[EnrollmentMode] = mapped_column(
        Enum(EnrollmentMode, name="enrollment_mode", values_callable=enum_values),
        nullable=False,
        default=EnrollmentMode.OPEN,
        server_default=EnrollmentMode.OPEN.value,
    )
    default_due_date_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Mirrors RealGuardianAccount's identical lockout columns
    # (services/auth/lockout.py) -- see that model for the full
    # PR #109 rationale.
    failed_login_attempts: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
