"""Unit tests: `get_or_grade_answer()`'s signature/version filter,
cosine-distance-ranked match, and fail-open behavior (spec 015
FR-002/FR-003/FR-004/FR-006/FR-008/FR-009, research.md §3).

Requires a reachable `DATABASE_URL` (mirrors `test_question_cache.py`)
-- `pgvector`'s cosine-distance query needs real Postgres. `embed_answer`
is patched everywhere (no real Voyage call in a unit test).
"""

import uuid
from unittest.mock import patch

import pytest

from src.models.grading_response_cache import GradingResponseCache
from src.services.cache_common.signature import compute_question_signature
from src.services.grading_cache.cache import get_or_grade_answer
from src.services.grading_client.client import GradingResult

pytestmark = pytest.mark.usefixtures("database_available")

QUESTION_STEM = "What is 2 + 2?"
RUBRIC_CRITERIA = [{"description": "states the correct sum", "weight": 1.0}]
GRADING_LOGIC_VERSION = "v2"
QUESTION_SIGNATURE = compute_question_signature(QUESTION_STEM, {"criteria": RUBRIC_CRITERIA})

# Orthogonal unit vectors -- identical embeddings are 0 cosine distance
# (well within threshold), orthogonal ones are 1.0 (well outside it).
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


async def _get_or_grade(db_session, *, grading_logic_version: str = GRADING_LOGIC_VERSION):
    calls = {"count": 0}

    async def grade_fn(**kwargs):
        calls["count"] += 1
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
    )
    return result, outcome, calls["count"]


async def test_no_matching_signature_is_a_miss(db_session):
    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls = await _get_or_grade(db_session)
    assert outcome.hit is False
    assert outcome.reason == "no_matching_entry"
    assert grade_calls == 1
    assert result.correct is False


async def test_matching_signature_and_version_within_threshold_is_a_hit(db_session):
    row = _add_row(db_session, question_signature=QUESTION_SIGNATURE)
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls = await _get_or_grade(db_session)

    assert outcome.hit is True
    assert outcome.cache_entry_id == row.cache_entry_id
    assert grade_calls == 0
    assert result.correct == row.correct
    assert result.graduated_score == row.graduated_score
    assert result.criteria_met == row.criteria_met


async def test_matching_signature_different_grading_logic_version_is_a_miss(db_session):
    _add_row(db_session, question_signature=QUESTION_SIGNATURE, grading_logic_version="stale-v1")
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert grade_calls == 1


async def test_similar_embedding_under_different_signature_is_a_miss(db_session):
    _add_row(db_session, question_signature="some-other-question-signature")
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert grade_calls == 1


async def test_dissimilar_embedding_same_signature_is_a_miss(db_session):
    _add_row(db_session, question_signature=QUESTION_SIGNATURE, embedding=_VEC_B)
    db_session.commit()

    with patch("src.services.grading_cache.cache.embed_answer", return_value=_VEC_A):
        result, outcome, grade_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert grade_calls == 1


async def test_embedding_failure_is_a_fail_open_miss(db_session):
    with patch("src.services.grading_cache.cache.embed_answer", side_effect=RuntimeError("boom")):
        result, outcome, grade_calls = await _get_or_grade(db_session)

    assert outcome.hit is False
    assert outcome.reason == "storage_failure"
    assert grade_calls == 1
