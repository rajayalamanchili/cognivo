import datetime
import uuid

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class RealInstructorAccount(Base):
    """An instructor's real, credential-holding account (spec 009, research.md
    §2). `email` is unique within this table only -- the same person may
    separately hold a `RealGuardianAccount` under the same email.

    `display_name` (spec 041 FR-017, data-model.md) is nullable at the DB
    level and never collected at registration -- `register_instructor` is
    unchanged. It's set only via `PATCH /api/auth/instructor/me`, required
    before `is_listed=True` can be set on any of this instructor's rosters
    (`services/roster/enrollment.py`), identically for a brand-new and a
    pre-existing account.
    """

    __tablename__ = "real_instructor_accounts"

    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
