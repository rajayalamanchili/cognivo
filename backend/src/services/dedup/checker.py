"""Near-duplicate question detection (FR-008, research.md §3).

Compares a newly generated question's stem against the learner's last N
generated questions for the same topic using `difflib.SequenceMatcher`'s
similarity ratio -- no embeddings/vector infrastructure, per research.md
§3's decision to keep `pgvector` scoped to Milestone 9's Tutor Agent
rather than pulling it forward for a 5-question lookback window.
"""

import difflib
import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from src.models.generated_question import GeneratedQuestion

DEFAULT_LOOKBACK = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.85


def is_near_duplicate(
    candidate_stem: str,
    previous_stems: Sequence[str],
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> bool:
    """True if `candidate_stem` is text-identical to, or similar enough
    to (similarity ratio >= `threshold`), any of `previous_stems`."""
    return any(
        difflib.SequenceMatcher(None, candidate_stem, previous_stem).ratio() >= threshold
        for previous_stem in previous_stems
    )


def recent_stems_for_topic(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    topic_id: str,
    limit: int = DEFAULT_LOOKBACK,
) -> list[str]:
    """The learner's last `limit` generated question stems for this
    topic, most-recent first -- the FR-008 lookback window. Questions
    are generated per learner (data-model.md's GeneratedQuestion), so
    this window is scoped to `learner_id` as well as `topic_id`."""
    rows = (
        db.query(GeneratedQuestion.stem)
        .filter(
            GeneratedQuestion.learner_id == learner_id,
            GeneratedQuestion.subject_id == subject_id,
            GeneratedQuestion.topic_id == topic_id,
        )
        .order_by(GeneratedQuestion.generated_at.desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]
