import datetime
import uuid

from sqlalchemy import DateTime, Enum, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import DeletionTargetType, enum_values


class DeletionRequest(Base):
    """spec 009's hard-delete tracking row (unchanged by this spec).
    `target_id` is deliberately not a FK -- by completion, the target row
    is gone (spec 009). Unenrollment (FR-007a) never creates one of
    these -- it only removes an `Enrollment` row; a `DeletionRequest`
    targeting a learner does cascade to remove that learner's
    `Enrollment`/`EnrollmentRequest` rows too, as one item in spec 009
    FR-005's full cascade.

    At most one pending (`completed_at IS NULL`) request may exist per
    `(target_type, target_id)` -- enforced by the partial unique index
    below, not just the app-level check-then-insert in `deletion.py`/
    `inactivity.py`/`execute.py`'s `_queue_guardian_deletion` (PR #79
    review: that check alone isn't race-proof), same pattern as
    `TutoringSession`'s active-session constraint."""

    __tablename__ = "deletion_requests"
    __table_args__ = (
        Index(
            "uq_deletion_requests_pending_target",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where="completed_at IS NULL",
        ),
    )

    deletion_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_type: Mapped[DeletionTargetType] = mapped_column(
        Enum(DeletionTargetType, name="deletion_target_type", values_callable=enum_values),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_by: Mapped[str] = mapped_column(nullable=False)
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
