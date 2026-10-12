import datetime
import uuid

from sqlalchemy import DateTime, Enum, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import AuthorizedByType, enum_values


class PasswordResetToken(Base):
    """spec 045 data-model.md. `account_id` is deliberately not a FK --
    points at `real_guardian_accounts.guardian_id` or
    `real_instructor_accounts.instructor_id` depending on `account_type`,
    same non-FK pattern as `DeletionRequest.target_id`. Only `token_hash`
    (SHA-256 of the raw emailed token) is ever persisted -- the raw
    value itself never touches the database (research.md §2).

    Validity is checked at verification time (`used_at IS NULL AND
    expires_at > now()`), never swept."""

    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index(
            "uq_password_reset_tokens_pending_account",
            "account_type",
            "account_id",
            unique=True,
            postgresql_where="used_at IS NULL",
        ),
    )

    reset_token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_type: Mapped[AuthorizedByType] = mapped_column(
        Enum(AuthorizedByType, name="authorized_by_type", values_callable=enum_values),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
