from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class GradeBand(Base):
    """A declared grade (1-12) a subject's content spans (FR-001).

    A minimal existence table -- no metadata beyond `grade` itself
    (research.md Decision 9); a subject with zero `GradeBand` rows is
    fully ungraded (FR-009). `Topic.grade`, when set, MUST reference a
    row here (data-model.md).
    """

    __tablename__ = "grade_bands"
    __table_args__ = (CheckConstraint("grade BETWEEN 1 AND 12", name="ck_grade_bands_grade_range"),)

    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.subject_id"), primary_key=True)
    grade: Mapped[int] = mapped_column(Integer, primary_key=True)
