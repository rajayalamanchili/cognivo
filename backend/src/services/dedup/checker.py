"""Near-duplicate question detection (FR-008, research.md §3).

Compares a newly generated question's stem embedding against the
learner's last N generated questions for the same topic using cosine
similarity (bug-fix amendment, 2026-10-12, research.md §7-10) --
previously a raw-text `difflib.SequenceMatcher` ratio, which
false-positived on two legitimately distinct questions sharing a
phrasing template but differing only in their numeric values (e.g. two
different factored quadratics), disproportionately starving
single-topic quizzes of fresh questions.
"""

import logging
import math
import os
import time
import uuid
from collections.abc import Sequence

import litellm
from sqlalchemy.orm import Session

from src.models.generated_question import GeneratedQuestion

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK = 5
# Cosine similarity, not a difflib text ratio (was 0.85) -- same name,
# new value and meaning. Implementer-chosen starting point per
# Clarifications 2026-10-12, not derived from a calibration study,
# backstopped by this module's own true-negative/true-positive tests.
DEFAULT_SIMILARITY_THRESHOLD = 0.92
# Raised from 3 (Clarifications, 2026-10-12) -- shared by every caller
# instead of each defining its own independent literal.
DEFAULT_MAX_DEDUP_ATTEMPTS = 5

MAX_EMBED_ATTEMPTS = 2
EMBED_RETRY_DELAY_SECONDS = 2


class EmbeddingUnavailableError(Exception):
    """Every attempt to embed the given stem failed (e.g. a transient
    network error, or a Voyage rate-limit/billing rejection) -- mirrors
    `services/retrieval/passage_search.py`'s and
    `services/misconception/embed.py`'s error of the same name."""


def embed_stem(stem: str) -> list[float]:
    """Embeds one question stem for near-duplicate comparison. Own small
    wrapper, not a shared cross-module helper -- matches this project's
    established convention (`misconception/embed.py`'s docstring):
    same-model reuse via `litellm`, not a shared private function."""
    model_name = os.environ.get("TUTOR_EMBEDDING_MODEL", "voyage/voyage-3")
    last_error: Exception | None = None
    for attempt in range(MAX_EMBED_ATTEMPTS):
        try:
            response = litellm.embedding(model=model_name, input=[stem])
            return response.data[0]["embedding"]
        except Exception as exc:  # noqa: BLE001 -- any provider failure retries, then surfaces
            last_error = exc
            if attempt < MAX_EMBED_ATTEMPTS - 1:
                time.sleep(EMBED_RETRY_DELAY_SECONDS)
    raise EmbeddingUnavailableError() from last_error


def embed_stem_or_none(stem: str) -> list[float] | None:
    """`embed_stem`, failing open to `None` (logged) instead of raising --
    the shape every dedup-check and persist-time call site wants
    (research.md §10): a near-duplicate check is a quality safeguard,
    not a correctness invariant, so a Voyage outage should never block
    question generation or persistence. A `None` result is excluded
    from comparison by `is_near_duplicate`, never treated as a match or
    non-match."""
    try:
        return embed_stem(stem)
    except EmbeddingUnavailableError:
        logger.warning("dedup: embedding unavailable, failing open for stem dedup/storage")
        return None


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def is_near_duplicate(
    candidate_embedding: list[float] | None,
    previous: Sequence[tuple[str, list[float] | None]],
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> bool:
    """True if `candidate_embedding` is cosine-similar enough (ratio >=
    `threshold`) to any embedding in `previous`. Fails open (`False`) if
    `candidate_embedding` is `None` (the candidate itself couldn't be
    embedded) -- any `previous` entry with a `None` embedding (a
    pre-migration row, or one that failed to embed at write time) is
    simply excluded from comparison, not treated as a match or
    non-match."""
    if candidate_embedding is None:
        return False
    return any(
        _cosine_similarity(candidate_embedding, embedding) >= threshold
        for _, embedding in previous
        if embedding is not None
    )


def recent_stems_for_topic(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    topic_id: str,
    limit: int = DEFAULT_LOOKBACK,
) -> list[tuple[str, list[float] | None]]:
    """The learner's last `limit` generated (stem, stem_embedding) pairs
    for this topic, most-recent first -- the FR-008 lookback window.
    Questions are generated per learner (data-model.md's
    GeneratedQuestion), so this window is scoped to `learner_id` as well
    as `topic_id`. `stem_embedding` is `None` for any pre-migration row
    (bug-fix amendment, 2026-10-12)."""
    rows = (
        db.query(GeneratedQuestion.stem, GeneratedQuestion.stem_embedding)
        .filter(
            GeneratedQuestion.learner_id == learner_id,
            GeneratedQuestion.subject_id == subject_id,
            GeneratedQuestion.topic_id == topic_id,
        )
        .order_by(GeneratedQuestion.generated_at.desc())
        .limit(limit)
        .all()
    )
    return [(row[0], row[1]) for row in rows]
