"""Deterministic structured-answer grading (FR-009).

No LLM judgment call: `multiple_choice` is exact-match against
`answer_key`; `numeric` is a relative-tolerance comparison against the
question's own `answer_key`-supplied tolerance (generated alongside the
question, not a single global constant -- see GeneratedQuestion in
data-model.md).
"""

from typing import Any

from src.models.enums import QuestionType


def validate_response_shape(question_type: QuestionType, response: Any) -> None:
    """Raises `ValueError` if `response`'s Python type doesn't match what
    `question_type` expects: an integer option index for
    `multiple_choice`, a number for `numeric`. `bool` is rejected
    outright even though Python's `bool` is an `int` subclass -- a
    boolean is never a valid option index or numeric answer."""
    if isinstance(response, bool):
        raise ValueError("boolean response is not a valid answer")
    if question_type == QuestionType.MULTIPLE_CHOICE:
        if not isinstance(response, int):
            raise ValueError("multiple_choice response must be an integer option index")
    elif question_type == QuestionType.NUMERIC:
        if not isinstance(response, (int, float)):
            raise ValueError("numeric response must be a number")
    elif question_type == QuestionType.FREE_TEXT:
        if not isinstance(response, str):
            raise ValueError("free_text response must be a string")


def grade_answer(question: dict[str, Any], *, response: Any) -> bool:
    """`question` needs `question_type` and `answer_key` matching
    GeneratedQuestion's shape: `{"correct_index": int}` for
    multiple_choice, `{"value": float, "tolerance": float}` for numeric.
    """
    question_type = question["question_type"]
    answer_key = question["answer_key"]

    if question_type == QuestionType.MULTIPLE_CHOICE:
        return _grade_multiple_choice(answer_key, response)
    if question_type == QuestionType.NUMERIC:
        return _grade_numeric(answer_key, response)
    raise ValueError(f"unknown question_type: {question_type!r}")


def _grade_multiple_choice(answer_key: dict[str, Any], response: Any) -> bool:
    correct_index = answer_key["correct_index"]
    return type(response) is type(correct_index) and response == correct_index


def _grade_numeric(answer_key: dict[str, Any], response: Any) -> bool:
    correct_value = float(answer_key["value"])
    tolerance = float(answer_key["tolerance"])
    response_value = float(response)

    if correct_value == 0.0:
        return response_value == 0.0

    relative_error = abs(response_value - correct_value) / abs(correct_value)
    return relative_error <= tolerance
