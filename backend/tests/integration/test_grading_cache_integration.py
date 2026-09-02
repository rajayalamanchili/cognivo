"""Integration test: `get_or_grade_answer()` serves a second, differently
-worded but semantically equivalent answer from cache without a second
Grading Agent call, and never leaks the first learner's answer text to
the second (spec 015 User Story 2, FR-002/FR-003/FR-009).
"""

import uuid
from unittest.mock import patch

import pytest

from src.services.grading_cache.cache import get_or_grade_answer
from src.services.grading_client.client import GradingResult

pytestmark = pytest.mark.usefixtures("database_available")

QUESTION_STEM = "Why does a plant need sunlight?"
RUBRIC_CRITERIA = [{"description": "mentions photosynthesis", "weight": 1.0}]
GRADING_LOGIC_VERSION = "v2"

# A single shared vector stands in for "these two answers embed to
# (near-)identical points" -- the real embedding call is mocked, so the
# actual wording below is irrelevant to whether this test hits or misses.
_SHARED_EMBEDDING = [1.0] + [0.0] * 1023


async def test_second_semantically_equivalent_answer_is_a_hit_with_no_answer_text_leak(
    db_session,
):
    grade_fn = _spy_grade_fn(GradingResult(
        correct=True,
        graduated_score=0.95,
        criteria_met=["mentions photosynthesis"],
        criteria_missed=[],
        grading_logic_version=GRADING_LOGIC_VERSION,
    ))

    with patch(
        "src.services.grading_cache.cache.embed_answer", return_value=_SHARED_EMBEDDING
    ):
        first_result, first_outcome = await get_or_grade_answer(
            db_session,
            question_stem=QUESTION_STEM,
            rubric_criteria=RUBRIC_CRITERIA,
            learner_answer="Plants use sunlight to make food through photosynthesis.",
            question_id=uuid.uuid4(),
            learner_id=uuid.uuid4(),
            grading_logic_version=GRADING_LOGIC_VERSION,
            grade_fn=grade_fn,
        )
        db_session.commit()
        assert first_outcome.hit is False
        assert grade_fn.calls == 1

        second_result, second_outcome = await get_or_grade_answer(
            db_session,
            question_stem=QUESTION_STEM,
            rubric_criteria=RUBRIC_CRITERIA,
            learner_answer="Sunlight lets plants photosynthesize and produce their own energy.",
            question_id=uuid.uuid4(),
            learner_id=uuid.uuid4(),
            grading_logic_version=GRADING_LOGIC_VERSION,
            grade_fn=grade_fn,
        )

    assert second_outcome.hit is True
    assert grade_fn.calls == 1  # not invoked again
    assert second_result == first_result
    assert "Plants use sunlight" not in str(second_result)
    assert "Sunlight lets plants" not in str(first_result)


def _spy_grade_fn(result: GradingResult):
    async def grade_fn(**kwargs):
        grade_fn.calls += 1
        return result

    grade_fn.calls = 0
    return grade_fn
