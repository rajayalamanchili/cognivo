import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKeyConstraint, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import PassageField, enum_values

# voyage-3's output dimension (research.md §1) -- the embedding column's
# fixed width; TUTOR_EMBEDDING_MODEL is a runtime config value, but this
# dimension is a schema constant tied to the specific model this feature
# ships with.
EMBEDDING_DIMENSION = 1024


class ContentPassageEmbedding(Base):
    """One retrievable passage from a content-artifact field, embedded
    for `pgvector` similarity search (spec 012 research.md §5).

    One row per topic's `skill_definition.summary` plus each of its
    `difficulty_calibration` entries -- generated/upserted by
    `services/content_artifact/loader.py`'s load pipeline, never
    authored directly. A reload that bumps `Subject.content_version`
    regenerates all of that subject's passages; rows for a superseded
    `content_version` are deleted, not left to accumulate
    (data-model.md's validation rules).
    """

    __tablename__ = "content_passage_embeddings"
    __table_args__ = (
        # CASCADE: `persist_content_artifact` hard-deletes a Topic row
        # no longer listed in a reloaded artifact (loader.py's
        # docstring) -- without cascade, that delete would fail with a
        # dangling-FK violation against any embedding row still
        # referencing it (generate_passage_embeddings runs after
        # persist_content_artifact, so it can't clean these up first).
        ForeignKeyConstraint(
            ["subject_id", "topic_id"],
            ["topics.subject_id", "topics.topic_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "subject_id",
            "topic_id",
            "field",
            "content_version",
            name="uq_content_passage_embeddings_subject_topic_field_version",
        ),
    )

    passage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[str] = mapped_column(nullable=False)
    topic_id: Mapped[str] = mapped_column(nullable=False)
    field: Mapped[PassageField] = mapped_column(
        Enum(PassageField, name="passage_field", values_callable=enum_values), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    content_version: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
