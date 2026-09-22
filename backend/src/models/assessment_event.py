import datetime
import uuid

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import AssessmentEventType, enum_values


class AssessmentEvent(Base):
    """Append-only audit log row -- the FR-010/SC-006 audit trail.

    Distinct from, and in addition to, the Langfuse trace emitted per
    FR-014: this answers the pedagogical "why," Langfuse answers the
    technical "what happened inside the model call."

    `topic_id` is nullable to support spec 002's
    `recommendation_report_generated` event, which summarizes a whole
    report rather than a single topic -- every other event type still
    always sets a real `topic_id` (spec 002 data-model.md).
    """

    __tablename__ = "assessment_events"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]),
        # Partial unique index (e04658523ea2's migration creates it via raw
        # op.execute -- never declared here until spec 021 found the gap
        # via a real migration-vs-model schema-drift comparison). PR #18's
        # concurrent-double-submission race guard.
        Index(
            "ix_assessment_events_answer_submitted_question_id",
            "question_id",
            unique=True,
            postgresql_where=text("event_type = 'answer_submitted'"),
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), nullable=False
    )
    event_type: Mapped[AssessmentEventType] = mapped_column(
        Enum(AssessmentEventType, name="assessment_event_type", values_callable=enum_values),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_questions.question_id"), nullable=True
    )
    subject_id: Mapped[str] = mapped_column(nullable=False)
    topic_id: Mapped[str | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
