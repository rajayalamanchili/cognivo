import datetime
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, ForeignKeyConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import AssessmentEventType


class AssessmentEvent(Base):
    """Append-only audit log row -- the FR-010/SC-006 audit trail.

    Distinct from, and in addition to, the Langfuse trace emitted per
    FR-014: this answers the pedagogical "why," Langfuse answers the
    technical "what happened inside the model call."
    """

    __tablename__ = "assessment_events"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("demo_learner_profiles.learner_id"), nullable=False
    )
    event_type: Mapped[AssessmentEventType] = mapped_column(
        Enum(AssessmentEventType, name="assessment_event_type"), nullable=False
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_questions.question_id"), nullable=True
    )
    subject_id: Mapped[str] = mapped_column(nullable=False)
    topic_id: Mapped[str] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
