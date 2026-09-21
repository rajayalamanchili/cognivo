"""Unit tests: `is_read_aloud_eligible` (spec 019 FR-001/FR-003,
research.md Decision 1). Pure function, no DB.
"""

from src.services.mediation.read_aloud import is_read_aloud_eligible


def test_grades_one_and_two_are_eligible():
    assert is_read_aloud_eligible(1) is True
    assert is_read_aloud_eligible(2) is True


def test_grade_three_and_above_are_not_eligible():
    assert is_read_aloud_eligible(3) is False
    assert is_read_aloud_eligible(12) is False


def test_no_grade_progress_is_not_eligible():
    """FR-013: an ungraded subject (no `GradeProgress` row) must be
    entirely unaffected -- not eligible, same as today's behavior."""
    assert is_read_aloud_eligible(None) is False
