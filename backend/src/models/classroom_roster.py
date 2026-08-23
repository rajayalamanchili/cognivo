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
    per-subject shape. `join_code` is generated for every roster
    regardless of mode (data-model.md's Correction) -- it's the only
    field `POST /api/rosters/join` uses to identify the target roster;
    the API layer hides it in the create/PATCH response for a `closed`
    roster, but the column itself is never null.

    `instructor_id` is deliberately not a FK (migration `7e686faa5e6d`,
    `/speckit-clarify`) -- it points at either a `RealInstructorAccount`
    or a `DemoInstructorProfile` row depending on which kind of session
    created this roster, same reasoning as `RetentionRecord.account_id`/
    `DeletionRequest.target_id`. Enforced at the application layer:
    every write path derives this value from `current_instructor`
    (`services/auth/dependencies.py`), never from unvalidated input."""

    __tablename__ = "classroom_rosters"

    roster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), nullable=False)
    enrollment_mode: Mapped[EnrollmentMode] = mapped_column(
        Enum(EnrollmentMode, name="enrollment_mode", values_callable=enum_values), nullable=False
    )
    join_code: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
