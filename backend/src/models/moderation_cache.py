import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ModerationCache(Base):
    """A cached moderation guardrail verdict, keyed on an exact signature
    of the normalized submitted text and the moderation instruction
    version (spec 026 FR-001, FR-003, FR-005, data-model.md §1).

    Deliberately stores no raw submitted text (FR-008) -- only its
    signature, which is not reversible to the original text. No cap or
    TTL in this milestone -- only a `moderation_instruction_version`
    mismatch makes a row unreachable.
    """

    __tablename__ = "moderation_cache"
    __table_args__ = (
        Index(
            "ix_moderation_cache_lookup",
            "text_signature",
            "moderation_instruction_version",
        ),
    )

    cache_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    text_signature: Mapped[str] = mapped_column(Text, nullable=False)
    moderation_instruction_version: Mapped[str] = mapped_column(nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_served_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
