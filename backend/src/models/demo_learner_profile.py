import datetime
import uuid

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class DemoLearnerProfile(Base):
    """Milestone 1's lightweight seeded learner.

    `is_demo` MUST be explicitly set `true` at seed time -- never
    inferred (Constitution Principle VIII). No real-learner-data path
    exists in Milestone 1.
    """

    __tablename__ = "demo_learner_profiles"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
