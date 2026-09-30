import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ShieldingClassificationCache(Base):
    """A cached Tutor Agent shielding-match verdict, keyed on an exact
    signature of the normalized (open-question-stem, tutor-message) pair
    and the shielding-classification instruction version (spec 026
    FR-002, FR-003, FR-004, FR-005, data-model.md §2).

    `pair_signature` is order-sensitive (`compute_paired_signature`) --
    this is what makes matching scoped per open question (FR-004).
    Deliberately stores no raw open-question or tutor-message text
    (FR-008) -- only the combined signature. No cap or TTL in this
    milestone -- only an instruction-version mismatch makes a row
    unreachable.
    """

    __tablename__ = "shielding_classification_cache"
    __table_args__ = (
        Index(
            "ix_shielding_classification_cache_lookup",
            "pair_signature",
            "shielding_classification_instruction_version",
        ),
    )

    cache_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pair_signature: Mapped[str] = mapped_column(Text, nullable=False)
    shielding_classification_instruction_version: Mapped[str] = mapped_column(nullable=False)
    matches: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_served_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
