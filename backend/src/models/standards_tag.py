from sqlalchemy import ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class StandardsTag(Base):
    """A real-world curriculum standard (e.g. a Common Core Math code)
    tagged on a graded topic (spec 038 FR-001).

    One row per (topic, standard) pairing -- a topic with two tags is two
    rows. The composite PK makes an exact-duplicate tag on one topic a
    schema-level impossibility. `title` is not part of the key; when the
    same `(framework, code)` pair recurs across topics, the validator
    (FR-012) guarantees every occurrence carries the identical title, so
    which row's `title` is read is never ambiguous.
    """

    __tablename__ = "standards_tags"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"],
            name="fk_standards_tags_subject_id_topic_id",
        ),
    )

    subject_id: Mapped[str] = mapped_column(String, primary_key=True)
    topic_id: Mapped[str] = mapped_column(String, primary_key=True)
    framework: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
