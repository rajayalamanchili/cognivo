import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import QuizSessionStatus, enum_values


class PracticeSession(Base):
    """A bounded, timed practice run (spec 022 data-model.md).

    Created only when a learner opts into a timer for ordinary practice
    (FR-008) -- never for today's untimed, unbounded practice, which
    stays exactly as stateless as it is today. Shaped like `QuizSession`
    (thin header row, score derived at read time from
    `GeneratedQuestion`/`AssessmentEvent`), reusing `QuizSessionStatus`
    rather than a duplicate enum. Unlike a quiz, practice has no
    pre-committed topic list or question count -- it ends only by timer
    expiry or manual early-end.
    """

    __tablename__ = "practice_sessions"

    practice_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), nullable=False)
    # NOT NULL, unlike QuizSession.time_limit_seconds -- this table only
    # exists for timed sessions (data-model.md).
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
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
