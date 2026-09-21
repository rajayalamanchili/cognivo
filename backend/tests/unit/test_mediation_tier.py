"""Unit tests: `determine_mediation_tier` (spec 019 FR-004,
research.md Decision 3). Pure function, no DB.
"""

from src.models.enums import MediationTier
from src.services.mediation.tier import determine_mediation_tier


def test_grades_one_and_two_are_co_present():
    assert determine_mediation_tier(1) == MediationTier.CO_PRESENT
    assert determine_mediation_tier(2) == MediationTier.CO_PRESENT


def test_grades_three_to_five_are_check_in():
    assert determine_mediation_tier(3) == MediationTier.CHECK_IN
    assert determine_mediation_tier(5) == MediationTier.CHECK_IN


def test_grades_six_to_eight_are_opt_in_nudges():
    assert determine_mediation_tier(6) == MediationTier.OPT_IN_NUDGES
    assert determine_mediation_tier(8) == MediationTier.OPT_IN_NUDGES


def test_grades_nine_to_twelve_are_independent():
    assert determine_mediation_tier(9) == MediationTier.INDEPENDENT
    assert determine_mediation_tier(12) == MediationTier.INDEPENDENT


def test_no_grade_progress_returns_none():
    """FR-013: an ungraded subject (no `GradeProgress` row) has no tier
    applied at all -- distinguishable from `CO_PRESENT`, even though
    every call site treats the two identically."""
    assert determine_mediation_tier(None) is None
