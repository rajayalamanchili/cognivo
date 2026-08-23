import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import EnrollmentMode, enum_values


class ClassroomRoster(Base):
    """One instructor's subject-scoped class (data-model.md). `subject_id`
    fills the gap spec 009 left undetermined -- a roster is scoped to
    exactly one subject, matching `build_weak_area_report`'s own
    per-subject shape. `join_code` is meaningful only when
    `enrollment_mode` is `open`."""

    __tablename__ = "classroom_rosters"

    roster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("real_instructor_accounts.instructor_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), nullable=False)
    enrollment_mode: Mapped[EnrollmentMode] = mapped_column(
        Enum(EnrollmentMode, name="enrollment_mode", values_callable=enum_values), nullable=False
    )
    join_code: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
