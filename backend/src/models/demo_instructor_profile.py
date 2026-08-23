import datetime
import uuid

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DemoInstructorProfile(Base):
    """Milestone 1's `LearnerProfile` demo-row pattern, extended to
    instructors (FR-014). Kept as its own table -- mirroring the
    pre-existing separation between `LearnerProfile` and
    `RealInstructorAccount` -- rather than a nullable-`is_demo` row
    inside `RealInstructorAccount`, so a demo instructor never needs a
    password/credential at all.

    `is_demo` MUST be explicitly set `true` at seed time -- never
    inferred (Constitution Principle VIII).
    """

    __tablename__ = "demo_instructor_profiles"

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
