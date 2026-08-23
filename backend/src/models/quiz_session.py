import datetime
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import QuizSessionStatus, enum_values


class QuizSession(Base):
    """A bounded, named adaptive-difficulty quiz (spec 005 data-model.md).

    A thin persisted header row only -- the ordered list of questions
    answered, their correctness, and the resulting score/summary are all
    derived at read time from `GeneratedQuestion`/`AssessmentEvent` rows
    tagged with this session's id, never duplicated here (Clarifications,
    2026-08-18). An abandoned quiz is simply one left `IN_PROGRESS`
    forever; nothing actively transitions it to a distinct status.
    """

    __tablename__ = "quiz_sessions"

    quiz_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), nullable=False)
    topic_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[QuizSessionStatus] = mapped_column(
        Enum(QuizSessionStatus, name="quiz_session_status", values_callable=enum_values),
        nullable=False,
        default=QuizSessionStatus.IN_PROGRESS,
    )
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
