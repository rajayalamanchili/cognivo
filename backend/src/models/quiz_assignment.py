import datetime
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class QuizAssignment(Base):
    """An instructor-configured quiz targeted at a subset (or all) of a
    roster's enrolled learners (spec 011 data-model.md). A pure header
    row -- the targeted learners live in `QuizAssignmentTarget`, and each
    target's actual attempt is an ordinary, entirely-unmodified
    `QuizSession` (spec 005). Not editable in place: `cancelled_at` is
    the only post-creation transition (research.md §6).
    """

    __tablename__ = "quiz_assignments"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    roster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classroom_rosters.roster_id"), nullable=False
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("real_instructor_accounts.instructor_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), nullable=False)
    topic_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    due_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
