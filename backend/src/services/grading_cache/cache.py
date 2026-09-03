"""Cross-learner cache in front of the Grading Agent's A2A call (spec
015 FR-002/FR-003/FR-004/FR-006/FR-008/FR-009, research.md §3,
Clarifications 2026-09-02).

Keyed on `question_signature` -- the same content hash `question_cache/
cache.py` computes and stores, since every generated question is its own
per-learner row (`GeneratedQuestion.learner_id` NOT NULL) and can't be
keyed on `question_id` -- plus `grading_logic_version`, then ranked by
`pgvector` cosine distance between the new answer's embedding and each
matching row's stored `answer_embedding`.

Embedding distance alone is deliberately NOT sufficient to serve a hit
(FR-003): validated live against Milestone 6's real ground-truth grading
eval set (`backend/scripts/validate_grading_cache_threshold.py`), no
single cosine-distance threshold can separate negation/opposite-meaning
answers from genuine paraphrases -- the closest false-positive pair
measured a smaller distance than genuine true-positive pairs. Instead,
distance narrows to a single closest candidate within a loose
`PREFILTER_DISTANCE_CEILING` (efficiency only, not a correctness
boundary), and `equivalence.py`'s cheap rubric-criteria re-classification
is the actual gate: only a `criteria_met` pattern match confirms the
candidate before its cached grade is served. This never compares the new
answer against the original learner's raw answer text -- the cache
stores none of it (FR-009).

`grade_fn`/`verify_fn` are both called with the exact kwargs the real
`grade_free_text_answer`/`matches_cached_criteria_pattern` functions
take, rather than caller-prebuilt zero-arg closures -- this wrapper
already receives every argument either needs as its own parameters, so
the real functions are passed straight through in production and fakes
are substituted in tests.

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

# Cosine distance -- a loose efficiency-only pre-filter (module
# docstring), not a correctness boundary: the ground-truth validation
# never saw a same-question pair exceed ~0.24, so this leaves generous
# margin while still skipping the equivalence check's model call for
# genuinely unrelated (e.g. blank/off-topic) answers.
PREFILTER_DISTANCE_CEILING = 0.5


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
    verify_fn: Callable[..., Awaitable[bool]],
) -> tuple[GradingResult, CacheOutcome]:
    """Serves a hit only when a candidate is both embedding-close (within
    `PREFILTER_DISTANCE_CEILING`, same `question_signature` +
    `grading_logic_version`) AND confirmed by `verify_fn(...)`'s
    rubric-criteria re-classification (FR-003). Otherwise calls
    `grade_fn(...)` and stores its result as a new row.

    Fails open (FR-008): any exception embedding the answer, querying
    the cache, or verifying a candidate is treated as a miss, never
    raised -- `grade_fn(...)` still runs so the request itself always
    succeeds. A failure writing the fresh result back is swallowed the
    same way; caching is a best-effort optimization, never a
    request-blocking dependency.
    """
    question_signature = compute_question_signature(question_stem, {"criteria": rubric_criteria})

    storage_failed = False
    answer_embedding: list[float] | None = None
    candidate_row: GradingResponseCache | None = None
    try:
        answer_embedding = embed_answer(question_stem, learner_answer)
        distance_expr = GradingResponseCache.answer_embedding.cosine_distance(answer_embedding)
        match = (
            db.query(GradingResponseCache, distance_expr.label("distance"))
            .filter(
                GradingResponseCache.question_signature == question_signature,
                GradingResponseCache.grading_logic_version == grading_logic_version,
                distance_expr <= PREFILTER_DISTANCE_CEILING,
            )
            .order_by(distance_expr)
            .first()
        )
        if match is not None:
            candidate_row, _distance = match
    except Exception:  # noqa: BLE001 -- any lookup/embedding failure fails open (FR-008)
        storage_failed = True

    miss_reason: str | None = None
    if candidate_row is not None:
        try:
            confirmed = await verify_fn(
                question_stem=question_stem,
                rubric_criteria=rubric_criteria,
                learner_answer=learner_answer,
                cached_criteria_met=candidate_row.criteria_met,
            )
        except Exception:  # noqa: BLE001 -- a verification failure fails open (FR-008)
            confirmed = False
            miss_reason = "verification_failed"

        if confirmed:
            candidate_row.hit_count += 1
            candidate_row.last_served_at = datetime.datetime.now(datetime.UTC)
            db.flush()
            return (
                _result_from_cache_row(candidate_row),
                CacheOutcome(hit=True, cache_entry_id=candidate_row.cache_entry_id),
            )
        if miss_reason is None:
            miss_reason = "not_equivalent"
    elif storage_failed:
        miss_reason = "storage_failure"
    else:
        miss_reason = "no_matching_entry"

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
