import datetime
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import MasteryBand, mastery_band_for


class MasteryState(Base):
    """One row per (learner, topic) pair -- only for topics with >=1 answer.

    No row means "unknown" (FR-005): a query-time absence check, never a
    stored zero/default. `band` is intentionally NOT a column here --
    data-model.md requires it be derived from `p_mastery` (and
    `consecutive_mastered_observations` below) at read time (see
    models.enums.mastery_band_for) so the two can never drift.
    """

    __tablename__ = "mastery_states"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learner_profiles.learner_id"), primary_key=True
    )
    subject_id: Mapped[str] = mapped_column(primary_key=True)
    topic_id: Mapped[str] = mapped_column(primary_key=True)
    p_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    update_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_mastered_observations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    @property
    def band(self) -> MasteryBand:
        return mastery_band_for(self.p_mastery, self.consecutive_mastered_observations)
