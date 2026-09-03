"""Unit tests: `get_or_grade_answer()`'s signature/version filter,
embedding pre-filter, rubric-criteria equivalence gate, and fail-open
behavior (spec 015 FR-002/FR-003/FR-004/FR-006/FR-008/FR-009,
research.md §3, Clarifications 2026-09-02).

Requires a reachable `DATABASE_URL` (mirrors `test_question_cache.py`)
-- `pgvector`'s cosine-distance query needs real Postgres. `embed_answer`
is patched everywhere (no real Voyage call in a unit test); `verify_fn`
is a fake passed directly (an injectable parameter, no ADK/LLM machinery
needed to test the gating logic itself -- `equivalence.py`'s own prompt/
classification behavior is exercised live by
`scripts/validate_grading_cache_threshold.py`, not here).
"""

import uuid
from unittest.mock import patch

import pytest

from src.models.grading_response_cache import GradingResponseCache
from src.services.cache_common.signature import compute_question_signature
from src.services.grading_cache.cache import PREFILTER_DISTANCE_CEILING, get_or_grade_answer
from src.services.grading_client.client import GradingResult

pytestmark = pytest.mark.usefixtures("database_available")

QUESTION_STEM = "What is 2 + 2?"
RUBRIC_CRITERIA = [{"description": "states the correct sum", "weight": 1.0}]
GRADING_LOGIC_VERSION = "v2"
QUESTION_SIGNATURE = compute_question_signature(QUESTION_STEM, {"criteria": RUBRIC_CRITERIA})

# Orthogonal unit vectors -- identical embeddings are 0 cosine distance
# (well within the pre-filter), orthogonal ones are 1.0 (well beyond it).
_VEC_A = [1.0] + [0.0] * 1023
_VEC_B = [0.0, 1.0] + [0.0] * 1022


def _add_row(
    db_session,
    *,
    question_signature: str,
    embedding: list[float] = _VEC_A,
    grading_logic_version: str = GRADING_LOGIC_VERSION,
) -> GradingResponseCache:
    row = GradingResponseCache(
        question_signature=question_signature,
        answer_embedding=embedding,
        grading_logic_version=grading_logic_version,
        correct=True,
        graduated_score=0.9,
        criteria_met=["states the correct sum"],
        criteria_missed=[],
    )
    db_session.add(row)
    db_session.flush()
    return row


def _verify_fn(*, result: bool = True, raises: bool = False):
    calls = {"count": 0}

    async def _fn(**kwargs):
        calls["count"] += 1
        if raises:
            raise RuntimeError("boom")
        return result

    _fn.calls = calls
    return _fn


async def _get_or_grade(
    db_session,
    *,
    verify_fn=None,
    grading_logic_version: str = GRADING_LOGIC_VERSION,
):
    grade_calls = {"count": 0}
    verify = verify_fn or _verify_fn()

    async def grade_fn(**kwargs):
        grade_calls["count"] += 1
        return GradingResult(
            correct=False,
            graduated_score=0.2,
            criteria_met=[],
            criteria_missed=["states the correct sum"],
            grading_logic_version=grading_logic_version,
        )

    result, outcome = await get_or_grade_answer(
        db_session,
        question_stem=QUESTION_STEM,
        rubric_criteria=RUBRIC_CRITERIA,
        learner_answer="four",
        question_id=uuid.uuid4(),
        learner_id=uuid.uuid4(),
        grading_logic_version=grading_logic_version,
        grade_fn=grade_fn,
        verify_fn=verify,
    )
    return result, outcome, grade_calls["count"], verify.calls["count"]


async def test_no_matching_signature_is_a_miss(db_session):
    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(db_session)
    assert outcome.hit is False
    assert outcome.reason == "no_matching_entry"
    assert grade_calls == 1
    assert verify_calls == 0
    assert result.correct is False


async def test_matching_signature_and_version_within_prefilter_confirmed_is_a_hit(db_session):
    row = _add_row(db_session, question_signature=QUESTION_SIGNATURE)
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(
            db_session, verify_fn=_verify_fn(result=True)
        )

    assert outcome.hit is True
    assert outcome.cache_entry_id == row.cache_entry_id
    assert grade_calls == 0
    assert verify_calls == 1
    assert result.correct == row.correct
    assert result.graduated_score == row.graduated_score
    assert result.criteria_met == row.criteria_met


async def test_candidate_within_prefilter_but_not_confirmed_is_a_miss(db_session):
    _add_row(db_session, question_signature=QUESTION_SIGNATURE)
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(
            db_session, verify_fn=_verify_fn(result=False)
        )

    assert outcome.hit is False
    assert outcome.reason == "not_equivalent"
    assert grade_calls == 1
    assert verify_calls == 1


async def test_verification_failure_fails_open_to_a_miss(db_session):
    _add_row(db_session, question_signature=QUESTION_SIGNATURE)
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(
            db_session, verify_fn=_verify_fn(raises=True)
        )

    assert outcome.hit is False
    assert outcome.reason == "verification_failed"
    assert grade_calls == 1
    assert verify_calls == 1


async def test_matching_signature_different_grading_logic_version_is_a_miss(db_session):
    _add_row(db_session, question_signature=QUESTION_SIGNATURE, grading_logic_version="stale-v1")
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert grade_calls == 1
    assert verify_calls == 0


async def test_similar_embedding_under_different_signature_is_a_miss(db_session):
    _add_row(db_session, question_signature="some-other-question-signature")
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert grade_calls == 1
    assert verify_calls == 0


async def test_embedding_beyond_prefilter_ceiling_is_a_miss_without_verifying(db_session):
    assert PREFILTER_DISTANCE_CEILING < 1.0  # orthogonal (distance 1.0) must fall outside it
    _add_row(db_session, question_signature=QUESTION_SIGNATURE, embedding=_VEC_B)
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert outcome.reason == "no_matching_entry"
    assert grade_calls == 1
    assert verify_calls == 0


async def test_embedding_failure_is_a_fail_open_miss(db_session):
    with patch("src.services.grading_cache.cache.embed_answer", side_effect=RuntimeError("boom")):
        result, outcome, grade_calls, verify_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert outcome.reason == "storage_failure"
    assert grade_calls == 1
    assert verify_calls == 0
