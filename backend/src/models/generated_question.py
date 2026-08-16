import datetime
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import DifficultyBand, QuestionType, ValidationStatus


class GeneratedQuestion(Base):
    """A single dynamically generated structured question.

    `answer_key` is generated together with `stem`/`options`, never
    after the fact (FR-007, Constitution Principle II). A question must
    reach `validation_status == VALID` before `shown_at` may be set.
    """

    __tablename__ = "generated_questions"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]),
    )

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("demo_learner_profiles.learner_id"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(nullable=False)
    topic_id: Mapped[str] = mapped_column(nullable=False)
    difficulty: Mapped[DifficultyBand] = mapped_column(
        Enum(DifficultyBand, name="difficulty_band"), nullable=False
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type"), nullable=False
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer_key: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"),
        nullable=False,
        default=ValidationStatus.PENDING,
    )
    flagged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("demo_learner_profiles.learner_id"), nullable=True
    )
    flagged_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    shown_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
