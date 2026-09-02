"""Unit tests: `get_or_generate_question()`'s pool lookup, eviction,
freshness-window, and fail-open behavior (spec 015 FR-001/FR-006/FR-008/
FR-012, research.md §2).

Requires a reachable `DATABASE_URL` (mirrors `test_passage_search.py`).
Skips otherwise.
"""

import datetime
import uuid
from unittest.mock import patch

import pytest

from src.agents.assessment_gen.agent import GeneratedQuestionDraft
from src.models.enums import DifficultyBand, QuestionType
from src.models.question_generation_cache import QuestionGenerationCache
from src.services.question_cache.cache import POOL_SIZE, get_or_generate_question

pytestmark = pytest.mark.usefixtures("database_available")

CONTENT_VERSION = "v1"
GENERATION_PROMPT_VERSION = "v1"
DIFFICULTY = DifficultyBand.EASY


def _draft(stem: str) -> GeneratedQuestionDraft:
    return GeneratedQuestionDraft(
        question_type="multiple_choice",
        stem=stem,
        options=["a", "b", "c", "d"],
        correct_index=0,
    )


def _add_pool_row(
    db_session,
    *,
    topic_id: str,
    stem: str,
    content_version: str = CONTENT_VERSION,
    generation_prompt_version: str = GENERATION_PROMPT_VERSION,
    created_at: datetime.datetime | None = None,
) -> QuestionGenerationCache:
    row = QuestionGenerationCache(
        subject_id="algebra-1",
        topic_id=topic_id,
        difficulty=DIFFICULTY,
        content_version=content_version,
        generation_prompt_version=generation_prompt_version,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem=stem,
        options=["a", "b", "c", "d"],
        answer_key={"correct_index": 0},
        question_signature=f"sig-{uuid.uuid4()}",
    )
    db_session.add(row)
    db_session.flush()
    if created_at is not None:
        row.created_at = created_at
        db_session.flush()
    return row


async def _get_or_generate(db_session, *, topic_id, avoid_stems=(), generated_stem="fresh stem"):
    calls = {"count": 0}

    async def generate_fn():
        calls["count"] += 1
        return _draft(generated_stem)

    draft, outcome = await get_or_generate_question(
        db_session,
        subject_id="algebra-1",
        topic_id=topic_id,
        difficulty=DIFFICULTY,
        content_version=CONTENT_VERSION,
        generation_prompt_version=GENERATION_PROMPT_VERSION,
        avoid_stems=avoid_stems,
        generate_fn=generate_fn,
    )
    return draft, outcome, calls["count"]


async def test_empty_pool_is_a_miss_and_inserts_a_row(db_session, algebra_subject):
    draft, outcome, generate_calls = await _get_or_generate(
        db_session, topic_id="integers-and-operations", generated_stem="brand new question"
    )
    assert outcome.hit is False
    assert outcome.reason == "no_matching_entry"
    assert generate_calls == 1
    assert draft.stem == "brand new question"
    stored = (
        db_session.query(QuestionGenerationCache)
        .filter(QuestionGenerationCache.topic_id == "integers-and-operations")
        .all()
    )
    assert len(stored) == 1
    assert stored[0].stem == "brand new question"


async def test_non_duplicate_pool_entry_is_a_hit_without_calling_generator(
    db_session, algebra_subject
):
    row = _add_pool_row(
        db_session, topic_id="variables-and-expressions", stem="What is x in 2x = 4?"
    )
    db_session.commit()

    draft, outcome, generate_calls = await _get_or_generate(
        db_session, topic_id="variables-and-expressions"
    )
    assert outcome.hit is True
    assert outcome.cache_entry_id == row.cache_entry_id
    assert generate_calls == 0
    assert draft.stem == "What is x in 2x = 4?"


async def test_all_pool_entries_near_duplicate_of_avoid_stems_is_a_miss(
    db_session, algebra_subject
):
    _add_pool_row(
        db_session, topic_id="order-of-operations", stem="Evaluate 2 + 3 * 4 using PEMDAS."
    )
    db_session.commit()

    draft, outcome, generate_calls = await _get_or_generate(
        db_session,
        topic_id="order-of-operations",
        avoid_stems=["Evaluate 2 + 3 * 4 using PEMDAS."],
        generated_stem="a genuinely new question",
    )
    assert outcome.hit is False
    assert generate_calls == 1
    assert draft.stem == "a genuinely new question"

    stored = (
        db_session.query(QuestionGenerationCache)
        .filter(QuestionGenerationCache.topic_id == "order-of-operations")
        .all()
    )
    assert len(stored) == 2


async def test_eviction_keeps_pool_at_five_newest_entries(db_session, algebra_subject):
    now = datetime.datetime.now(datetime.UTC)
    for i in range(POOL_SIZE):
        _add_pool_row(
            db_session,
            topic_id="solving-one-step-equations",
            stem=f"stale stem {i}",
            created_at=now - datetime.timedelta(minutes=POOL_SIZE - i),
        )
    db_session.commit()

    # None of the 5 existing entries match this learner's avoid_stems,
    # so every one is filtered out -> miss -> a 6th row is inserted.
    draft, outcome, generate_calls = await _get_or_generate(
        db_session,
        topic_id="solving-one-step-equations",
        avoid_stems=[f"stale stem {i}" for i in range(POOL_SIZE)],
        generated_stem="the newest stem",
    )
    assert outcome.hit is False
    assert generate_calls == 1

    stored = (
        db_session.query(QuestionGenerationCache)
        .filter(QuestionGenerationCache.topic_id == "solving-one-step-equations")
        .all()
    )
    assert len(stored) == POOL_SIZE
    assert "the newest stem" in {row.stem for row in stored}
    assert "stale stem 0" not in {row.stem for row in stored}


async def test_entry_older_than_24_hours_is_excluded_and_treated_as_a_miss(
    db_session, algebra_subject
):
    stale_created_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=25)
    _add_pool_row(
        db_session,
        topic_id="solving-multi-step-equations",
        stem="an old, expired question",
        created_at=stale_created_at,
    )
    db_session.commit()

    draft, outcome, generate_calls = await _get_or_generate(
        db_session,
        topic_id="solving-multi-step-equations",
        generated_stem="a fresh replacement",
    )
    assert outcome.hit is False
    assert generate_calls == 1
    assert draft.stem == "a fresh replacement"


async def test_entry_with_different_content_version_is_never_returned(db_session, algebra_subject):
    _add_pool_row(
        db_session,
        topic_id="integers-and-operations",
        stem="a question from an old content version",
        content_version="stale-version",
    )
    db_session.commit()

    draft, outcome, generate_calls = await _get_or_generate(
        db_session, topic_id="integers-and-operations", generated_stem="a current-version question"
    )
    assert outcome.hit is False
    assert generate_calls == 1
    assert draft.stem == "a current-version question"


async def test_entry_with_different_generation_prompt_version_is_never_returned(
    db_session, algebra_subject
):
    _add_pool_row(
        db_session,
        topic_id="variables-and-expressions",
        stem="a question from an old prompt version",
        generation_prompt_version="stale-prompt-version",
    )
    db_session.commit()

    draft, outcome, generate_calls = await _get_or_generate(
        db_session,
        topic_id="variables-and-expressions",
        generated_stem="a current-prompt-version question",
    )
    assert outcome.hit is False
    assert generate_calls == 1
    assert draft.stem == "a current-prompt-version question"


async def test_lookup_failure_is_a_miss_and_the_generator_still_runs(db_session, algebra_subject):
    _add_pool_row(db_session, topic_id="order-of-operations", stem="a question that would hit")
    db_session.commit()

    with patch(
        "src.services.question_cache.cache.is_near_duplicate", side_effect=RuntimeError("boom")
    ):
        draft, outcome, generate_calls = await _get_or_generate(
            db_session, topic_id="order-of-operations", generated_stem="fresh despite the failure"
        )
    assert outcome.hit is False
    assert outcome.reason == "storage_failure"
    assert generate_calls == 1
    assert draft.stem == "fresh despite the failure"
