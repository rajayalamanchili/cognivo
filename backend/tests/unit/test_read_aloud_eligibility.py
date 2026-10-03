"""Unit tests: `is_read_aloud_eligible` (spec 019 FR-001/FR-003,
research.md Decision 1). Pure function, no DB. Unconditional as of the
2026-10-03 Clarification -- no longer grade-gated.
"""

from src.services.mediation.read_aloud import is_read_aloud_eligible


def test_every_grade_is_eligible():
    assert is_read_aloud_eligible(1) is True
    assert is_read_aloud_eligible(2) is True
    assert is_read_aloud_eligible(3) is True
    assert is_read_aloud_eligible(12) is True


def test_no_grade_progress_is_still_eligible():
    """An ungraded subject (no `GradeProgress` row) is eligible too --
    read-aloud no longer derives from grade at all."""
    assert is_read_aloud_eligible(None) is True
