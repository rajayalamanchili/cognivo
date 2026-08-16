"""Unit tests: deterministic structured-answer grading (FR-009, T028)."""

from src.models.enums import QuestionType
from src.services.mastery.grading import grade_answer


def _mc_question(correct_index: int = 1):
    return {
        "question_type": QuestionType.MULTIPLE_CHOICE,
        "answer_key": {"correct_index": correct_index},
    }


def _numeric_question(value: float, tolerance: float):
    return {
        "question_type": QuestionType.NUMERIC,
        "answer_key": {"value": value, "tolerance": tolerance},
    }


def test_multiple_choice_exact_match_correct():
    assert grade_answer(_mc_question(correct_index=2), response=2) is True


def test_multiple_choice_exact_match_incorrect():
    assert grade_answer(_mc_question(correct_index=2), response=0) is False


def test_multiple_choice_string_index_does_not_coerce_to_match():
    # response types must match the answer_key's index type: no silent
    # int/str coercion that could make an unintended option "correct".
    assert grade_answer(_mc_question(correct_index=2), response="2") is False


def test_numeric_within_relative_tolerance_is_correct():
    q = _numeric_question(value=100.0, tolerance=0.005)  # ±0.5%
    assert grade_answer(q, response=100.5) is True
    assert grade_answer(q, response=99.5) is True


def test_numeric_outside_relative_tolerance_is_incorrect():
    q = _numeric_question(value=100.0, tolerance=0.005)
    assert grade_answer(q, response=101.0) is False
    assert grade_answer(q, response=98.9) is False


def test_numeric_at_exact_tolerance_boundary_is_correct():
    q = _numeric_question(value=200.0, tolerance=0.01)  # ±1% -> ±2.0
    assert grade_answer(q, response=202.0) is True
    assert grade_answer(q, response=198.0) is True


def test_numeric_zero_correct_value_requires_exact_match():
    q = _numeric_question(value=0.0, tolerance=0.005)
    assert grade_answer(q, response=0.0) is True
    assert grade_answer(q, response=0.01) is False


def test_numeric_exact_match_is_correct():
    q = _numeric_question(value=42.0, tolerance=0.005)
    assert grade_answer(q, response=42.0) is True
