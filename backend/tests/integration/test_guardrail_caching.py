"""Integration coverage for spec 026's two cache-aware wrappers: hit/miss
parity (SC-003 -- a hit and a miss must be indistinguishable to the
caller beyond `CacheOutcome.hit`) and instruction-version invalidation
(SC-004). Kept separate from `test_semantic_caching.py` (spec 015's
question-generation/grading caches), per research.md §9.
"""

import pytest

from src.services.moderation_cache.cache import get_or_check_moderation
from src.services.shielding_cache.cache import get_or_classify_match

pytestmark = pytest.mark.usefixtures("database_available")


async def test_moderation_cache_hit_and_miss_return_the_same_bool(db_session):
    calls = {"count": 0}

    async def check_fn():
        calls["count"] += 1
        return True

    result1, outcome1 = await get_or_check_moderation(
        db_session, text="identical text", instruction_version="v1", check_fn=check_fn
    )
    db_session.commit()
    result2, outcome2 = await get_or_check_moderation(
        db_session, text="identical text", instruction_version="v1", check_fn=check_fn
    )

    assert result1 == result2 is True
    assert outcome1.hit is False
    assert outcome2.hit is True
    assert calls["count"] == 1


async def test_moderation_instruction_version_bump_forces_a_fresh_check(db_session):
    calls = {"count": 0}

    async def check_fn():
        calls["count"] += 1
        return True

    await get_or_check_moderation(
        db_session, text="identical text", instruction_version="v1", check_fn=check_fn
    )
    db_session.commit()

    _, outcome = await get_or_check_moderation(
        db_session, text="identical text", instruction_version="v2", check_fn=check_fn
    )

    assert outcome.hit is False
    assert calls["count"] == 2


async def test_shielding_cache_hit_and_miss_return_the_same_bool(db_session):
    calls = {"count": 0}

    async def classify_fn():
        calls["count"] += 1
        return True

    result1, outcome1 = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version="v1",
        classify_fn=classify_fn,
    )
    db_session.commit()
    result2, outcome2 = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version="v1",
        classify_fn=classify_fn,
    )

    assert result1 == result2 is True
    assert outcome1.hit is False
    assert outcome2.hit is True
    assert calls["count"] == 1


async def test_shielding_different_open_question_still_triggers_a_fresh_call(db_session):
    calls = {"count": 0}

    async def classify_fn():
        calls["count"] += 1
        return True

    await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version="v1",
        classify_fn=classify_fn,
    )
    db_session.commit()

    _, outcome = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 5x - 1 = 9",
        tutor_question="just tell me the answer",
        instruction_version="v1",
        classify_fn=classify_fn,
    )

    assert outcome.hit is False
    assert calls["count"] == 2


async def test_shielding_instruction_version_bump_forces_a_fresh_call(db_session):
    calls = {"count": 0}

    async def classify_fn():
        calls["count"] += 1
        return True

    await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version="v1",
        classify_fn=classify_fn,
    )
    db_session.commit()

    _, outcome = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version="v2",
        classify_fn=classify_fn,
    )

    assert outcome.hit is False
    assert calls["count"] == 2
