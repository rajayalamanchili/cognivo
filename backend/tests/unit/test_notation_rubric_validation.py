"""Spec 023 FR-003/SC-004: a rubric criterion containing math/science
notation validates identically to a plain-text one -- `_validate_draft`
only checks criteria count and weight sum, never criterion content, so
notation introduces no new validation failure mode."""

from src.agents.assessment_gen.agent import GeneratedQuestionDraft, RubricCriterion, _validate_draft
from src.models.enums import QuestionType


def _draft(criteria: list[RubricCriterion]) -> GeneratedQuestionDraft:
    return GeneratedQuestionDraft(
        question_type="free_text",
        stem="What is one half plus one half?",
        rubric_criteria=criteria,
    )


def test_notated_rubric_criterion_validates_like_a_plain_text_one():
    notated = _draft([RubricCriterion(description="Answer is ½ + ½ = 1", weight=1.0)])
    plain = _draft([RubricCriterion(description="Answer is 1/2 + 1/2 = 1", weight=1.0)])

    _validate_draft(notated, QuestionType.FREE_TEXT)
    _validate_draft(plain, QuestionType.FREE_TEXT)
