import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import AuthorizedByType, enum_values


class Enrollment(Base):
    """A learner's active membership in a roster (data-model.md). Deleting
    this row *is* unenrollment (FR-007a) -- no soft-delete/status column;
    the row's existence is the enrollment's existence. Unique on
    (`learner_id`, `roster_id`): a learner enrolls in a given roster at
    most once at a time -- re-enrolling after unenrollment creates a new
    row."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("learner_id", "roster_id", name="uq_enrollments_learner_roster"),
    )

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), nullable=False
    )
    roster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classroom_rosters.roster_id"), nullable=False
    )
    enrolled_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    authorized_by_type: Mapped[AuthorizedByType] = mapped_column(
        Enum(AuthorizedByType, name="authorized_by_type", values_callable=enum_values),
        nullable=False,
    )
    authorized_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
