import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class LearnerProfile(Base):
    """A learner -- demo (Milestone 1) or real (spec 010).

    `is_demo` MUST be explicitly set at creation time -- never inferred
    (Constitution Principle VIII). A demo row leaves `guardian_id`/
    `retention_record_id` null, exactly as before this rename; a real row
    sets both non-null at creation time (application-level enforcement,
    not a DB constraint -- data-model.md's Correction explains why: no
    portable "nullable iff is_demo" check without a trigger).

    Renamed from `DemoLearnerProfile` (data-model.md's Correction to
    spec 009's originally-proposed separate `RealLearnerAccount` table,
    found incompatible with 5 existing hard FKs to this table).
    """

    __tablename__ = "learner_profiles"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    guardian_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("real_guardian_accounts.guardian_id"), nullable=True
    )
    retention_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retention_records.retention_record_id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
