from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.subject import Subject


class Topic(Base):
    """Node in a subject's topic graph.

    `topic_id` is only unique within its `subject_id`, so the primary
    key is composite. `order_index` is set at load time from the
    content artifact's declaration order -- it is the deterministic
    tiebreaker the Sequencing Agent's next-topic eligibility rule uses
    when multiple topics tie on `p_mastery` (FR-006).
    """

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("subject_id", "order_index", name="uq_topics_subject_order_index"),
    )

    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(nullable=False)
    is_entry_level: Mapped[bool] = mapped_column(Boolean, nullable=False)
    skill_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    subject: Mapped["Subject"] = relationship(back_populates="topics")
