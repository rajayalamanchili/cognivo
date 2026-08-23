import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import EnrollmentDecision, enum_values


class EnrollmentRequest(Base):
    """A pending (or decided) join request for a `closed` roster
    (data-model.md, FR-006). Only created for a closed roster's join
    attempt -- an open roster's join creates an `Enrollment` directly. A
    second join attempt for the same (`learner_id`, `roster_id`) pair
    while a request is already pending returns the existing pending
    request rather than creating a duplicate (Edge Cases,
    services/roster/enrollment.py)."""

    __tablename__ = "enrollment_requests"

    enrollment_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), nullable=False
    )
    roster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classroom_rosters.roster_id"), nullable=False
    )
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision: Mapped[EnrollmentDecision | None] = mapped_column(
        Enum(EnrollmentDecision, name="enrollment_decision", values_callable=enum_values),
        nullable=True,
    )
