import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base

# voyage-3's output dimension -- matches
# src/models/content_passage_embedding.py's EMBEDDING_DIMENSION.
EMBEDDING_DIMENSION = 1024


class GradingResponseCache(Base):
    """A cached free-text grading result, matched by the specific
    question's content-hash `question_signature` (spec 015 research.md
    §3 -- every generated question is its own per-learner row, so this
    can't key on `question_id` directly) plus a `pgvector`-matched
    embedding of the learner's answer (spec 015 FR-002/FR-003/FR-004,
    data-model.md §2).

    Deliberately stores no raw answer text and no `learner_id` (FR-009)
    -- only what's needed to reproduce the grade, never anything that
    could leak the original submitter's identity or exact wording to a
    different learner on a hit. No cap or TTL in this milestone
    (research.md §6) -- only a `grading_logic_version` mismatch makes a
    row unreachable.
    """

    __tablename__ = "grading_response_cache"
    __table_args__ = (
        Index(
            "ix_grading_response_cache_lookup",
            "question_signature",
            "grading_logic_version",
        ),
        Index(
            "ix_grading_response_cache_embedding_cosine",
            "answer_embedding",
            postgresql_using="hnsw",
            postgresql_ops={"answer_embedding": "vector_cosine_ops"},
        ),
    )

    cache_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question_signature: Mapped[str] = mapped_column(Text, nullable=False)
    answer_embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=False
    )
    grading_logic_version: Mapped[str] = mapped_column(nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    graduated_score: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_met: Mapped[list] = mapped_column(JSON, nullable=False)
    criteria_missed: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_served_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
