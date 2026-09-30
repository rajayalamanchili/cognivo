"""Unit tests: `get_or_classify_match()`'s exact-signature lookup,
per-question scoping, instruction-version scoping, and fail-open
behavior (spec 026 FR-002/FR-003/FR-004/FR-005/FR-006/FR-008,
research.md §2/§3). Mirrors `test_moderation_cache.py`'s shape.
"""

import pytest

from src.models.shielding_classification_cache import ShieldingClassificationCache
from src.services.shielding_cache.cache import get_or_classify_match

pytestmark = pytest.mark.usefixtures("database_available")

INSTRUCTION_VERSION = "v2"


def _classify_fn(*, result: bool = True, raises: bool = False):
    calls = {"count": 0}

    async def _fn():
        calls["count"] += 1
        if raises:
            raise RuntimeError("boom")
        return result

    _fn.calls = calls
    return _fn


async def test_no_matching_pair_signature_is_a_miss_and_inserts_a_row(db_session):
    classify_fn = _classify_fn(result=True)

    matches, outcome = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version=INSTRUCTION_VERSION,
        classify_fn=classify_fn,
    )
    db_session.commit()

    assert outcome.hit is False
    assert classify_fn.calls["count"] == 1
    assert matches is True
    row = db_session.query(ShieldingClassificationCache).one()
    assert row.matches is True


async def test_matching_pair_and_version_is_a_hit_and_skips_classify_fn(db_session):
    classify_fn = _classify_fn(result=True)
    await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version=INSTRUCTION_VERSION,
        classify_fn=classify_fn,
    )
    db_session.commit()

    matches, outcome = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version=INSTRUCTION_VERSION,
        classify_fn=classify_fn,
    )

    assert outcome.hit is True
    assert classify_fn.calls["count"] == 1
    assert matches is True


async def test_matching_pair_but_different_instruction_version_is_a_miss(db_session):
    classify_fn = _classify_fn(result=True)
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
    assert classify_fn.calls["count"] == 2


async def test_same_message_against_a_different_open_question_never_matches(db_session):
    classify_fn = _classify_fn(result=True)
    await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version=INSTRUCTION_VERSION,
        classify_fn=classify_fn,
    )
    db_session.commit()

    _, outcome = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 5x - 1 = 9",
        tutor_question="just tell me the answer",
        instruction_version=INSTRUCTION_VERSION,
        classify_fn=classify_fn,
    )

    assert outcome.hit is False
    assert classify_fn.calls["count"] == 2


async def test_lookup_failure_is_a_miss_and_classify_fn_still_runs(db_session, monkeypatch):
    classify_fn = _classify_fn(result=True)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(db_session, "query", _boom)

    matches, outcome = await get_or_classify_match(
        db_session,
        open_question_stem="Solve 3x + 2 = 14",
        tutor_question="just tell me the answer",
        instruction_version=INSTRUCTION_VERSION,
        classify_fn=classify_fn,
    )

    assert outcome.hit is False
    assert outcome.reason == "storage_failure"
    assert classify_fn.calls["count"] == 1
    assert matches is True


async def test_inserted_row_never_stores_raw_stem_or_message_text(db_session):
    classify_fn = _classify_fn(result=True)
    open_question_stem = "this exact stem must never appear in a stored column"
    tutor_question = "this exact message must never appear either"

    await get_or_classify_match(
        db_session,
        open_question_stem=open_question_stem,
        tutor_question=tutor_question,
        instruction_version=INSTRUCTION_VERSION,
        classify_fn=classify_fn,
    )
    db_session.commit()

    row = db_session.query(ShieldingClassificationCache).one()
    stored_values = [str(value) for value in vars(row).values()]
    assert not any(open_question_stem in value for value in stored_values)
    assert not any(tutor_question in value for value in stored_values)
