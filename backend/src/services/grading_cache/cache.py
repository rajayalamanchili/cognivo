"""Cross-learner cache in front of the Grading Agent's A2A call (spec
015 FR-002/FR-003/FR-004/FR-006/FR-008/FR-009, research.md §3).

Keyed on `question_signature` -- the same content hash `question_cache/
cache.py` computes and stores, since every generated question is its own
per-learner row (`GeneratedQuestion.learner_id` NOT NULL) and can't be
keyed on `question_id` -- plus `grading_logic_version`, then ranked by
`pgvector` cosine distance between the new answer's embedding and each
matching row's stored `answer_embedding`. Stores no raw answer text or
`learner_id` (FR-009): a hit is built purely from the matched row's
grade/rubric columns, so nothing from the original submitter's request
ever reaches a different learner.

`grade_fn` is called with the exact same kwargs `grade_free_text_answer`
already takes (`question_stem`/`rubric_criteria`/`learner_answer`/
`question_id`/`learner_id`) rather than a caller-prebuilt zero-arg
closure -- this wrapper already receives every one of those as its own
parameters, so the real function is passed straight through in
production and a fake is substituted in tests.

`grading_logic_version` is supplied by the caller, not discovered here:
it's a code constant living in the separately-deployed `grading-agent/`
service (A2A boundary, Constitution Principle VI) -- `questions.py`
reads it from the `GRADING_AGENT_LOGIC_VERSION` env var, mirroring
`GRADING_AGENT_URL`/`GRADING_AGENT_SHARED_SECRET`'s existing pattern for
keeping the two independently-deployed services in sync.
"""

import datetime
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from src.models.grading_response_cache import GradingResponseCache
from src.services.cache_common.outcome import CacheOutcome
from src.services.cache_common.signature import compute_question_signature
from src.services.grading_client.client import GradingResult
from src.services.misconception.embed import embed_answer

# Cosine distance, research.md §3 -- matches dedup/checker.py's 0.85
# cosine-similarity threshold for question-stem near-duplicates.
SIMILARITY_THRESHOLD = 0.15


def _result_from_cache_row(row: GradingResponseCache) -> GradingResult:
    return GradingResult(
        correct=row.correct,
        graduated_score=row.graduated_score,
        criteria_met=row.criteria_met,
        criteria_missed=row.criteria_missed,
        grading_logic_version=row.grading_logic_version,
    )


async def get_or_grade_answer(
    db: Session,
    *,
    question_stem: str,
    rubric_criteria: list[dict],
    learner_answer: str,
    question_id: uuid.UUID,
    learner_id: uuid.UUID,
    grading_logic_version: str,
    grade_fn: Callable[..., Awaitable[GradingResult]],
) -> tuple[GradingResult, CacheOutcome]:
    """Serves a semantically-close hit (same `question_signature` +
    `grading_logic_version`, cosine distance <= `SIMILARITY_THRESHOLD`)
    or calls `grade_fn(...)` and stores its result as a new row.

    Fails open (FR-008): any exception embedding the answer or querying
    the cache is treated as a miss (`reason="storage_failure"`), never
    raised -- `grade_fn(...)` still runs so the request itself always
    succeeds. A failure writing the fresh result back is swallowed the
    same way; caching is a best-effort optimization, never a
    request-blocking dependency.
    """
    question_signature = compute_question_signature(question_stem, {"criteria": rubric_criteria})

    storage_failed = False
    answer_embedding: list[float] | None = None
    hit_row: GradingResponseCache | None = None
    hit_distance: float | None = None
    try:
        answer_embedding = embed_answer(question_stem, learner_answer)
        distance_expr = GradingResponseCache.answer_embedding.cosine_distance(answer_embedding)
        match = (
            db.query(GradingResponseCache, distance_expr.label("distance"))
            .filter(
                GradingResponseCache.question_signature == question_signature,
                GradingResponseCache.grading_logic_version == grading_logic_version,
            )
            .order_by(distance_expr)
            .first()
        )
        if match is not None:
            hit_row, hit_distance = match
    except Exception:  # noqa: BLE001 -- any lookup/embedding failure fails open (FR-008)
        storage_failed = True

    if hit_row is not None and hit_distance is not None and hit_distance <= SIMILARITY_THRESHOLD:
        hit_row.hit_count += 1
        hit_row.last_served_at = datetime.datetime.now(datetime.UTC)
        db.flush()
        return (
            _result_from_cache_row(hit_row),
            CacheOutcome(hit=True, cache_entry_id=hit_row.cache_entry_id),
        )

    miss_reason = "storage_failure" if storage_failed else "no_matching_entry"

    result = await grade_fn(
        question_stem=question_stem,
        rubric_criteria=rubric_criteria,
        learner_answer=learner_answer,
        question_id=question_id,
        learner_id=learner_id,
    )

    if answer_embedding is not None:
        try:
            db.add(
                GradingResponseCache(
                    question_signature=question_signature,
                    answer_embedding=answer_embedding,
                    grading_logic_version=result.grading_logic_version,
                    correct=result.correct,
                    graduated_score=result.graduated_score,
                    criteria_met=result.criteria_met,
                    criteria_missed=result.criteria_missed,
                )
            )
            db.flush()
        except Exception:  # noqa: BLE001 -- best-effort write, never blocks the request (FR-008)
            pass

    return result, CacheOutcome(hit=False, reason=miss_reason)
