import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, func
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
    (`services/auth/dependencies.py`), never from unvalidated input.

    `grade` (spec 040 FR-009) is nullable and opt-in, mirroring
    `grade_bands`' own opt-in-per-subject precedent: an existing roster
    (or one created without declaring a grade) stays unrestricted, same
    as today. When declared, `services/roster/enrollment.py`'s
    `create_roster` validates it against the chosen subject's own
    `GradeBand` rows at creation time -- this is the only enforcement
    point (spec 040 research.md Decision 6): quiz assignments inherit a
    roster's `subject_id` directly (`quiz_assignment/assignment.py`),
    never taking one of their own, so there is nothing further to gate."""

    __tablename__ = "classroom_rosters"
    __table_args__ = (
        CheckConstraint(
            "grade IS NULL OR grade BETWEEN 1 AND 12", name="ck_classroom_rosters_grade_range"
        ),
    )

    roster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), nullable=False)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enrollment_mode: Mapped[EnrollmentMode] = mapped_column(
        Enum(EnrollmentMode, name="enrollment_mode", values_callable=enum_values), nullable=False
    )
    join_code: Mapped[str | None] = mapped_column(unique=True, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
