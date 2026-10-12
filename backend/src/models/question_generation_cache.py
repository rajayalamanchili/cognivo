import datetime
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Enum, ForeignKeyConstraint, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base
from src.models.enums import DifficultyBand, QuestionType, enum_values

# Same voyage-3/1024-dim model as GeneratedQuestion.stem_embedding --
# bug-fix amendment, 2026-10-12 (specs/005-adaptive-quiz/research.md §8;
# this table's own dedup-comparison role found during /speckit-implement,
# see this amendment's plan.md note).
EMBEDDING_DIMENSION = 1024


class QuestionGenerationCache(Base):
    """A rotating pool of up to 5 previously-validated, cross-learner
    question-generation results per `(subject_id, topic_id, difficulty,
    content_version, generation_prompt_version)` (spec 015 FR-001,
    FR-012, data-model.md §1).

    Pool-of-5 eviction happens at write time (`services/question_cache
    /cache.py`); the 24-hour freshness window is a read-time filter on
    `created_at`, not a stored expiry column -- a stale row is simply
    never matched, not deleted on a schedule (research.md §5).
    """

    __tablename__ = "question_generation_cache"
    __table_args__ = (
        ForeignKeyConstraint(["subject_id", "topic_id"], ["topics.subject_id", "topics.topic_id"]),
        Index(
            "ix_question_generation_cache_lookup",
            "subject_id",
            "topic_id",
            "difficulty",
            "content_version",
            "generation_prompt_version",
            "created_at",
        ),
    )

    cache_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subject_id: Mapped[str] = mapped_column(nullable=False)
    topic_id: Mapped[str] = mapped_column(nullable=False)
    difficulty: Mapped[DifficultyBand] = mapped_column(
        Enum(DifficultyBand, name="difficulty_band", values_callable=enum_values), nullable=False
    )
    content_version: Mapped[str] = mapped_column(nullable=False)
    generation_prompt_version: Mapped[str] = mapped_column(nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type", values_callable=enum_values), nullable=False
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    stem_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    """Set once at write time from `stem` (bug-fix amendment,
    2026-10-12) -- powers `is_near_duplicate` when a pool row is checked
    against a learner's `avoid_stems` in `get_or_generate_question`.
    `NULL` for every pre-migration row or one that failed to embed;
    excluded from comparison rather than treated as a match or
    non-match, same convention as `GeneratedQuestion.stem_embedding`."""
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer_key: Mapped[dict] = mapped_column(JSON, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_signature: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_served_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
