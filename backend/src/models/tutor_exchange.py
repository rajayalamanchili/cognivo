import datetime
import uuid

from sqlalchemy import ARRAY, JSON, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class TutorExchange(Base):
    """One question-answer turn within a `TutoringSession` (spec.md's
    "Tutor Exchange" entity) -- append-only within a session.

    `answer_text` stays `NULL` until the Tutor Agent's stream completes
    (FR-015's in-flight marker); `failed_at` is set instead on a stream
    failure/timeout, distinguishing "died mid-stream" from "still
    streaming" (`/speckit-analyze` finding H2, data-model.md). The two
    are mutually exclusive -- never both set on the same row.

    `shielded`/`shielded_question_id` (spec 016 FR-007) mirror
    `grounded`/`retrieved_passage_ids`'s existing shape: `shielded_
    question_id IS NOT NULL` implies `shielded = true`, but not the
    reverse -- an FR-010 inconclusive-determination shield can set
    `shielded = true` with no single triggering question identified
    (spec 016 data-model.md's invariant).
    """

    __tablename__ = "tutor_exchanges"

    exchange_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tutoring_sessions.session_id"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    grounded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieved_passage_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    delegation_context: Mapped[list | None] = mapped_column(JSON, nullable=True)
    failed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shielded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shielded_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_questions.question_id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
