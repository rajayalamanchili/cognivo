import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class QuizAssignmentTarget(Base):
    """One learner targeted by a `QuizAssignment` (spec 011 data-model.md).
    A snapshot taken at assignment-creation time -- never added to later
    (research.md §4). `quiz_session_id` is `NULL` until the learner's
    guardian starts the attempt, and is set exactly once: combined with
    the `UNIQUE (assignment_id, learner_id)` constraint below, this is
    the DB-enforced backing for FR-014's single-attempt rule
    (research.md §3). The attempt's own in-progress/completed/ended-early
    lifecycle is entirely `QuizSession`'s existing state machine (spec
    005), not re-modeled here -- status is derived at read time, never
    duplicated onto this row.
    """

    __tablename__ = "quiz_assignment_targets"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "learner_id", name="uq_quiz_assignment_targets_assignment_learner"
        ),
    )

    assignment_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_assignments.assignment_id"), nullable=False
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), nullable=False
    )
    quiz_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_sessions.quiz_session_id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
