import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.topic import Topic


class Subject(Base):
    """A top-level namespace for one domain-agnostic content artifact.

    `validated_at` is set only after the content artifact passes the
    load-time cycle/reachability check (FR-002); a subject with no
    `validated_at` MUST NOT be usable.
    """

    __tablename__ = "subjects"

    subject_id: Mapped[str] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(nullable=False)
    content_version: Mapped[str] = mapped_column(nullable=False)
    validated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    topics: Mapped[list["Topic"]] = relationship(back_populates="subject")
