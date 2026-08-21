"""Unit test: free-text rubric internal-consistency validation (spec 007
FR-002), T009.

A free-text question's rubric MUST have at least one criterion, and its
criteria weights MUST sum to ~1.0 -- both checked before the question
ever reaches a learner, the same generate-before-display gate
`test_question_validation.py` already exercises for multiple_choice and
numeric. No DB/LLM dependency -- exercises `_validate_draft` directly.
"""

import pytest

from src.agents.assessment_gen.agent import (
    GeneratedQuestionDraft,
    GenerationValidationError,
    RubricCriterion,
    _validate_draft,
)
from src.models.enums import QuestionType


def _free_text_draft(**overrides) -> GeneratedQuestionDraft:
    fields = {
        "question_type": "free_text",
        "stem": "Explain why water moves out of a cell placed in a hypertonic solution.",
        "options": None,
        "correct_index": None,
        "correct_value": None,
        "tolerance": None,
        "rubric_criteria": [
            RubricCriterion(description="mentions the concentration gradient", weight=0.5),
            RubricCriterion(
                description="states water moves toward higher solute concentration", weight=0.5
            ),
        ],
    }
    fields.update(overrides)
    return GeneratedQuestionDraft(**fields)


def test_valid_free_text_passes():
    _validate_draft(_free_text_draft(), QuestionType.FREE_TEXT)


def test_valid_single_criterion_passes():
    # A single all-encompassing criterion (weight 1.0) is a valid,
    # unremarkable case, not an error (spec.md FR-002).
    draft = _free_text_draft(
        rubric_criteria=[RubricCriterion(description="correctly explains osmosis", weight=1.0)]
    )
    _validate_draft(draft, QuestionType.FREE_TEXT)


def test_zero_criteria_rejected():
    draft = _free_text_draft(rubric_criteria=[])
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.FREE_TEXT)


def test_missing_criteria_rejected():
    draft = _free_text_draft(rubric_criteria=None)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.FREE_TEXT)


def test_weights_summing_below_one_rejected():
    draft = _free_text_draft(
        rubric_criteria=[RubricCriterion(description="mentions gradient", weight=0.3)]
    )
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.FREE_TEXT)


def test_weights_summing_above_one_rejected():
    draft = _free_text_draft(
        rubric_criteria=[
            RubricCriterion(description="mentions gradient", weight=0.7),
            RubricCriterion(description="mentions direction", weight=0.7),
        ]
    )
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.FREE_TEXT)


def test_weights_summing_to_approximately_one_passes():
    # Small floating-point slack (rel_tol=0.01) is intentional -- an LLM
    # producing 0.33/0.33/0.34 must not be rejected over rounding.
    draft = _free_text_draft(
        rubric_criteria=[
            RubricCriterion(description="a", weight=0.33),
            RubricCriterion(description="b", weight=0.33),
            RubricCriterion(description="c", weight=0.34),
        ]
    )
    _validate_draft(draft, QuestionType.FREE_TEXT)


def test_mismatched_question_type_rejected():
    draft = _free_text_draft()
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.NUMERIC)
