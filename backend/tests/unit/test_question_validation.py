"""Unit test: internal-consistency validation (SC-003), T042.

A question whose marked-correct option isn't among its listed options
MUST be rejected before it ever reaches a learner (FR-007). No DB/LLM
dependency -- exercises `_validate_draft` directly.
"""

import pytest

from src.agents.assessment_gen.agent import (
    GeneratedQuestionDraft,
    GenerationValidationError,
    _validate_draft,
)
from src.models.enums import QuestionType


def _mc_draft(**overrides) -> GeneratedQuestionDraft:
    fields = {
        "question_type": "multiple_choice",
        "stem": "What is 2 + 2?",
        "options": ["3", "4", "5", "6"],
        "correct_index": 1,
        "correct_value": None,
        "tolerance": None,
    }
    fields.update(overrides)
    return GeneratedQuestionDraft(**fields)


def _numeric_draft(**overrides) -> GeneratedQuestionDraft:
    fields = {
        "question_type": "numeric",
        "stem": "What is 10 / 4?",
        "options": None,
        "correct_index": None,
        "correct_value": 2.5,
        "tolerance": 0.005,
    }
    fields.update(overrides)
    return GeneratedQuestionDraft(**fields)


def test_valid_multiple_choice_passes():
    _validate_draft(_mc_draft(), QuestionType.MULTIPLE_CHOICE)


def test_valid_numeric_passes():
    _validate_draft(_numeric_draft(), QuestionType.NUMERIC)


def test_correct_index_out_of_range_rejected():
    draft = _mc_draft(correct_index=4)  # only indices 0-3 exist
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTIPLE_CHOICE)


def test_correct_index_negative_rejected():
    draft = _mc_draft(correct_index=-1)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTIPLE_CHOICE)


def test_correct_index_missing_rejected():
    draft = _mc_draft(correct_index=None)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTIPLE_CHOICE)


def test_too_few_options_rejected():
    draft = _mc_draft(options=["only one"], correct_index=0)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTIPLE_CHOICE)


def test_numeric_missing_correct_value_rejected():
    draft = _numeric_draft(correct_value=None)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.NUMERIC)


def test_numeric_missing_tolerance_rejected():
    draft = _numeric_draft(tolerance=None)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.NUMERIC)


def test_numeric_non_positive_tolerance_rejected():
    draft = _numeric_draft(tolerance=0.0)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.NUMERIC)


def test_mismatched_question_type_rejected():
    draft = _mc_draft()
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.NUMERIC)
