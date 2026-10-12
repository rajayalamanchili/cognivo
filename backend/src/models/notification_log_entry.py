import datetime
import uuid

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import AuthorizedByType, NotificationStatus, NotificationType, enum_values


class NotificationLogEntry(Base):
    """spec 045 data-model.md -- FR-012/FR-013's audit trail for every
    outbound notification email attempt, write-once/append-only.
    `account_id` is deliberately not a FK -- a deletion-request-
    confirmation log row must be able to outlive the just-deleted
    account it refers to (research.md §4), same reasoning as
    `DeletionRequest.target_id`."""

    __tablename__ = "notification_log_entries"

    notification_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", values_callable=enum_values),
        nullable=False,
    )
    account_type: Mapped[AuthorizedByType] = mapped_column(
        Enum(AuthorizedByType, name="authorized_by_type", values_callable=enum_values),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status", values_callable=enum_values),
        nullable=False,
    )
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
