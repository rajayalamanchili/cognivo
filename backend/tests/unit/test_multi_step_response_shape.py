"""Unit test: `validate_response_shape()`'s `multi_step` branch (spec 018
FR-003) -- a stepwise submission must be a list of strings, one per
expected step. No DB/LLM dependency, mirrors
`test_answer_rejects_image_payload.py`'s pure-function convention.
"""

import pytest

from src.models.enums import QuestionType
from src.services.mastery.grading import validate_response_shape


def test_list_of_strings_accepted():
    validate_response_shape(QuestionType.MULTI_STEP, ["3x = 12", "x = 4"])


def test_non_list_rejected():
    with pytest.raises(ValueError, match="multi_step response must be a list of strings"):
        validate_response_shape(QuestionType.MULTI_STEP, "3x = 12")


def test_list_with_non_string_entry_rejected():
    with pytest.raises(ValueError, match="multi_step response must be a list of strings"):
        validate_response_shape(QuestionType.MULTI_STEP, ["3x = 12", 4])


def test_empty_list_accepted_by_shape_check():
    # An empty list is shape-valid here -- the step-*count* check against
    # the question's own rubric (FR-012) is a separate, route-level
    # concern (contracts/api.md), not this generic type check.
    validate_response_shape(QuestionType.MULTI_STEP, [])
