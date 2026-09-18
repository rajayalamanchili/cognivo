"""Unit test: multi-step rubric internal-consistency validation (spec 018
FR-002/FR-005/FR-010).

A multi_step question's rubric MUST have at least 2 steps, and each
step's own criteria MUST have at least 2 entries (FR-005: a single
criterion per step can never distinguish a sound method with a
computational slip from a genuinely incorrect method) whose weights sum
to ~1.0 -- all checked before the question ever reaches a learner, the
same generate-before-display gate `test_assessment_gen_free_text.py`
exercises for free_text. No DB/LLM dependency -- exercises
`_validate_draft` directly.
"""

import pytest

from src.agents.assessment_gen.agent import (
    GeneratedQuestionDraft,
    GenerationValidationError,
    RubricCriterion,
    StepDraft,
    _validate_draft,
)
from src.models.enums import QuestionType


def _step(**overrides) -> StepDraft:
    fields = {
        "step_prompt": "Isolate the variable term on one side.",
        "rubric_criteria": [
            RubricCriterion(description="Chooses to subtract 2 from both sides", weight=0.5),
            RubricCriterion(description="Correctly computes 3x = 12", weight=0.5),
        ],
    }
    fields.update(overrides)
    return StepDraft(**fields)


def _multi_step_draft(**overrides) -> GeneratedQuestionDraft:
    fields = {
        "question_type": "multi_step",
        "stem": "Solve for x: 3x + 2 = 14",
        "options": None,
        "correct_index": None,
        "correct_value": None,
        "tolerance": None,
        "rubric_criteria": None,
        "steps": [
            _step(),
            _step(
                step_prompt="Solve for x.",
                rubric_criteria=[
                    RubricCriterion(description="Chooses to divide both sides by 3", weight=0.5),
                    RubricCriterion(description="Correctly computes x = 4", weight=0.5),
                ],
            ),
        ],
    }
    fields.update(overrides)
    return GeneratedQuestionDraft(**fields)


def test_valid_multi_step_draft_passes():
    _validate_draft(_multi_step_draft(), QuestionType.MULTI_STEP)


def test_single_step_rejected():
    draft = _multi_step_draft(steps=[_step()])
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTI_STEP)


def test_zero_steps_rejected():
    draft = _multi_step_draft(steps=[])
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTI_STEP)


def test_missing_steps_rejected():
    draft = _multi_step_draft(steps=None)
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTI_STEP)


def test_step_with_no_criteria_rejected():
    draft = _multi_step_draft(steps=[_step(rubric_criteria=[]), _step()])
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTI_STEP)


def test_step_with_exactly_one_criterion_rejected():
    # FR-005: a single criterion can't distinguish a computational slip
    # from a wrong method.
    draft = _multi_step_draft(
        steps=[
            _step(rubric_criteria=[RubricCriterion(description="Divides both sides", weight=1.0)]),
            _step(),
        ]
    )
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTI_STEP)


def test_step_weights_summing_below_one_rejected():
    draft = _multi_step_draft(
        steps=[
            _step(
                rubric_criteria=[
                    RubricCriterion(description="a", weight=0.2),
                    RubricCriterion(description="b", weight=0.2),
                ]
            ),
            _step(),
        ]
    )
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.MULTI_STEP)


def test_step_weights_summing_to_approximately_one_passes():
    draft = _multi_step_draft(
        steps=[
            _step(
                rubric_criteria=[
                    RubricCriterion(description="a", weight=0.33),
                    RubricCriterion(description="b", weight=0.34),
                    RubricCriterion(description="c", weight=0.33),
                ]
            ),
            _step(),
        ]
    )
    _validate_draft(draft, QuestionType.MULTI_STEP)


def test_mismatched_question_type_rejected():
    draft = _multi_step_draft()
    with pytest.raises(GenerationValidationError):
        _validate_draft(draft, QuestionType.FREE_TEXT)
