import datetime
import uuid

from sqlalchemy import Boolean, DateTime, String, false, func, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class RealGuardianAccount(Base):
    """A guardian's real, credential-holding account (spec 009, research.md
    §2). `email` is unique within this table only -- the same person may
    separately hold a `RealInstructorAccount` under the same email.

    `name` through `weekly_summary_enabled` are spec 041's Settings-page
    fields (data-model.md §`RealGuardianAccount`) -- flat columns on this
    entity, not a separate preferences table, mirroring
    `LearnerProfile.career_connections_enabled`'s own precedent.
    `password_changed_at` is spec 041's session-invalidation mechanism
    (research.md §6): `current_guardian` rejects a session token whose
    `iat` predates this timestamp, so it must stay `NULL` (not the
    account's `created_at`) until the first real password change --
    otherwise every token issued before this column existed would be
    retroactively invalidated.
    """

    __tablename__ = "real_guardian_accounts"

    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    read_aloud_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    larger_text: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    reduce_motion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    theme: Mapped[str] = mapped_column(
        String, nullable=False, default="system", server_default="system"
    )
    quiz_finished_email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    weekly_summary_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    password_changed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
