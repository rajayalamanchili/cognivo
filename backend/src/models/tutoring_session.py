import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import TutoringSessionStatus, enum_values


class TutoringSession(Base):
    """A bounded conversation between a learner and the Tutor Agent
    (spec.md's "Tutoring Session" entity), scoped to one subject.

    At most one `active` session may exist per `(learner_id,
    subject_id)` pair -- enforced by the partial unique index below,
    not just in application code (FR-014, research.md §8). `POST
    /api/tutor/sessions` is get-or-create against this constraint.
    """

    __tablename__ = "tutoring_sessions"
    __table_args__ = (
        Index(
            "uq_tutoring_sessions_active_learner_subject",
            "learner_id",
            "subject_id",
            unique=True,
            postgresql_where="status = 'active'",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), nullable=False
    )
    guardian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("real_guardian_accounts.guardian_id"), nullable=True
    )
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[TutoringSessionStatus] = mapped_column(
        Enum(TutoringSessionStatus, name="tutoring_session_status", values_callable=enum_values),
        nullable=False,
        default=TutoringSessionStatus.ACTIVE,
    )
