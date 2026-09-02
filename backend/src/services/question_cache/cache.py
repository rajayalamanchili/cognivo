"""Cross-learner cache in front of Assessment-Generation's model call
(spec 015 FR-001/FR-005/FR-006/FR-008/FR-012, research.md §2).

`get_or_generate_question` slots into the exact same generation-retry
loop `sequencing/agent.py`/`quiz/session.py` already had: a candidate
now comes from this pool first, a real `generate_fn()` call only on a
miss, keyed on `(subject_id, topic_id, difficulty, content_version,
generation_prompt_version)`. Learner-specific near-duplicate exclusion
(`avoid_stems`, Milestone 1's FR-008) is applied on top, unchanged --
caching never bypasses it (spec 015 FR-010).

Note: `image_url`/`image_alt_text` are columns on `QuestionGenerationCache`
(data-model.md §1, mirroring `GeneratedQuestion`'s shape) but are never
populated here -- unlike `stem`/`answer_key`, they aren't part of what
`generate_question` actually returns; the caller derives them fresh
from `Topic.image_asset` every time, hit or miss, so caching them here
would just be a stale copy of already-deterministic data.
"""

import datetime
import random
from collections.abc import Awaitable, Callable, Sequence

from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import (
    GeneratedQuestionDraft,
    RubricCriterion,
    draft_to_answer_key,
)
from src.models.enums import DifficultyBand, QuestionType
from src.models.question_generation_cache import QuestionGenerationCache
from src.services.cache_common.outcome import CacheOutcome
from src.services.cache_common.signature import compute_question_signature
from src.services.dedup.checker import is_near_duplicate

POOL_SIZE = 5
FRESHNESS_WINDOW_HOURS = 24


def _draft_from_cache_row(row: QuestionGenerationCache) -> GeneratedQuestionDraft:
    """Inverse of `draft_to_answer_key` -- rebuilds the draft shape a
    caller expects from a stored pool row's `question_type`/`stem`/
    `options`/`answer_key`."""
    kwargs: dict = {
        "question_type": row.question_type.value,
        "stem": row.stem,
        "options": row.options,
    }
    if row.question_type == QuestionType.MULTIPLE_CHOICE:
        kwargs["correct_index"] = row.answer_key["correct_index"]
    elif row.question_type == QuestionType.NUMERIC:
        kwargs["correct_value"] = row.answer_key["value"]
        kwargs["tolerance"] = row.answer_key["tolerance"]
    elif row.question_type == QuestionType.FREE_TEXT:
        kwargs["rubric_criteria"] = [
            RubricCriterion(description=criterion["description"], weight=criterion["weight"])
            for criterion in row.answer_key["criteria"]
        ]
    return GeneratedQuestionDraft(**kwargs)


def _key_filters(
    *,
    subject_id: str,
    topic_id: str,
    difficulty: DifficultyBand,
    content_version: str,
    generation_prompt_version: str,
) -> tuple:
    return (
        QuestionGenerationCache.subject_id == subject_id,
        QuestionGenerationCache.topic_id == topic_id,
        QuestionGenerationCache.difficulty == difficulty,
        QuestionGenerationCache.content_version == content_version,
        QuestionGenerationCache.generation_prompt_version == generation_prompt_version,
    )


def _evict_oldest_beyond_pool_size(db: Session, filters: tuple) -> None:
    ids_newest_first = [
        row.cache_entry_id
        for row in db.query(QuestionGenerationCache.cache_entry_id)
        .filter(*filters)
        .order_by(QuestionGenerationCache.created_at.desc())
        .all()
    ]
    stale_ids = ids_newest_first[POOL_SIZE:]
    if stale_ids:
        db.query(QuestionGenerationCache).filter(
            QuestionGenerationCache.cache_entry_id.in_(stale_ids)
        ).delete(synchronize_session=False)


async def get_or_generate_question(
    db: Session,
    *,
    subject_id: str,
    topic_id: str,
    difficulty: DifficultyBand,
    content_version: str,
    generation_prompt_version: str,
    generate_fn: Callable[[], Awaitable[GeneratedQuestionDraft]],
    avoid_stems: Sequence[str] = (),
) -> tuple[GeneratedQuestionDraft, CacheOutcome]:
    """Serves a pool hit (a previously-validated draft not near-duplicate
    of `avoid_stems`) or calls `generate_fn()` and stores its result as a
    new pool entry, evicting the oldest once the pool would exceed
    `POOL_SIZE` for this exact key (FR-012).

    Fails open (FR-008): any exception during the lookup is treated as a
    miss (`reason="storage_failure"`), never raised -- `generate_fn()`
    still runs so the request itself always succeeds. A failure writing
    the fresh result back to the pool is swallowed the same way; caching
    is a best-effort optimization, never a request-blocking dependency.
    """
    filters = _key_filters(
        subject_id=subject_id,
        topic_id=topic_id,
        difficulty=difficulty,
        content_version=content_version,
        generation_prompt_version=generation_prompt_version,
    )

    storage_failed = False
    candidates: list[QuestionGenerationCache] = []
    try:
        fresh_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            hours=FRESHNESS_WINDOW_HOURS
        )
        pool_rows = (
            db.query(QuestionGenerationCache)
            .filter(*filters, QuestionGenerationCache.created_at > fresh_cutoff)
            .all()
        )
        candidates = [row for row in pool_rows if not is_near_duplicate(row.stem, avoid_stems)]
    except Exception:  # noqa: BLE001 -- any lookup failure fails open (FR-008)
        storage_failed = True

    if candidates:
        row = random.choice(candidates)
        row.hit_count += 1
        row.last_served_at = datetime.datetime.now(datetime.UTC)
        db.flush()
        return _draft_from_cache_row(row), CacheOutcome(hit=True, cache_entry_id=row.cache_entry_id)

    miss_reason = "storage_failure" if storage_failed else "no_matching_entry"

    draft = await generate_fn()

    try:
        answer_key = draft_to_answer_key(draft)
        new_row = QuestionGenerationCache(
            subject_id=subject_id,
            topic_id=topic_id,
            difficulty=difficulty,
            content_version=content_version,
            generation_prompt_version=generation_prompt_version,
            question_type=QuestionType(draft.question_type),
            stem=draft.stem,
            options=draft.options,
            answer_key=answer_key,
            question_signature=compute_question_signature(draft.stem, answer_key),
        )
        db.add(new_row)
        db.flush()
        _evict_oldest_beyond_pool_size(db, filters)
    except Exception:  # noqa: BLE001 -- best-effort write, never blocks the request (FR-008)
        pass

    return draft, CacheOutcome(hit=False, reason=miss_reason)
