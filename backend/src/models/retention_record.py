import datetime
import uuid

from sqlalchemy import DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import (
    AuthorizedByType,
    RetentionAccountType,
    RetentionEnrollmentStatus,
    enum_values,
)


class RetentionRecord(Base):
    """spec 009's retention-tracking row (unchanged by this spec): drives
    FR-010's 1-year post-inactivity clock. `account_id` is deliberately
    not a FK -- it points at either a `LearnerProfile` or a
    `RealInstructorAccount` row depending on `account_type`, and a single
    column can't carry two different FK targets."""

    __tablename__ = "retention_records"

    retention_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_type: Mapped[RetentionAccountType] = mapped_column(
        Enum(RetentionAccountType, name="retention_account_type", values_callable=enum_values),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    authorized_by_type: Mapped[AuthorizedByType] = mapped_column(
        Enum(AuthorizedByType, name="authorized_by_type", values_callable=enum_values),
        nullable=False,
    )
    authorized_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    enrollment_status: Mapped[RetentionEnrollmentStatus] = mapped_column(
        Enum(
            RetentionEnrollmentStatus,
            name="retention_enrollment_status",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    became_inactive_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
