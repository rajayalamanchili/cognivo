import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class GradeProgress(Base):
    """A learner's current unlocked grade for one subject (FR-003/FR-004).

    `unlocked_grade` is set once at placement (the starting grade) and
    only ever increased afterward by the Sequencing Agent's unlock check
    -- a monotonic high-water mark, never recomputed down from live
    mastery state (data-model.md's Monotonicity note): already-unlocked
    grades must stay unlocked even if mastery on a lower grade's topic
    later regresses (spec.md Edge Cases).
    """

    __tablename__ = "grade_progress"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), primary_key=True
    )
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), primary_key=True)
    unlocked_grade: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
