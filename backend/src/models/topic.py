from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, ForeignKeyConstraint, Integer, UniqueConstraint
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

    `grade` is `NULL` for every topic in an ungraded subject (FR-009);
    when set, it MUST reference a `GradeBand` row for the same subject
    (research.md Decision 1's all-or-nothing rule, enforced at content-
    artifact validation time, not just by this FK).
    """

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("subject_id", "order_index", name="uq_topics_subject_order_index"),
        ForeignKeyConstraint(
            ["subject_id", "grade"], ["grade_bands.subject_id", "grade_bands.grade"],
            name="fk_topics_subject_id_grade",
        ),
    )

    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(nullable=False)
    is_entry_level: Mapped[bool] = mapped_column(Boolean, nullable=False)
    skill_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    image_asset: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)

    subject: Mapped["Subject"] = relationship(back_populates="topics")
