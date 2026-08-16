from sqlalchemy import ForeignKeyConstraint, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class PrerequisiteEdge(Base):
    """Directed edge in the topic graph: `from_topic` requires `to_topic`.

    Validated at content-artifact load time (FR-002): the directed graph
    over a subject's Topics/PrerequisiteEdges MUST be acyclic and every
    Topic MUST be reachable. See services/content_artifact/validator.py.
    """

    __tablename__ = "prerequisite_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_id", "from_topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        ForeignKeyConstraint(
            ["subject_id", "to_topic_id"], ["topics.subject_id", "topics.topic_id"]
        ),
        UniqueConstraint(
            "subject_id", "from_topic_id", "to_topic_id", name="uq_prerequisite_edges_triple"
        ),
    )

    edge_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[str] = mapped_column(nullable=False)
    from_topic_id: Mapped[str] = mapped_column(nullable=False)
    to_topic_id: Mapped[str] = mapped_column(nullable=False)
