"""Unit tests: mastery decay determinism and grace-period/half-life
behavior (research.md §5 item 1, FR-001/FR-008/FR-009/FR-010).
"""

import datetime

from src.services.mastery.decay import GRACE_PERIOD, HALF_LIFE, effective_mastery_for_review

_UPDATED_AT = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def test_within_grace_period_returns_raw_p_mastery():
    now = _UPDATED_AT + GRACE_PERIOD
    assert effective_mastery_for_review(0.85, updated_at=_UPDATED_AT, now=now) == 0.85


def test_past_grace_period_applies_exponential_decay():
    now = _UPDATED_AT + GRACE_PERIOD + HALF_LIFE
    result = effective_mastery_for_review(0.8, updated_at=_UPDATED_AT, now=now)
    assert result == 0.4


def test_decay_approaches_but_never_reaches_zero():
    now = _UPDATED_AT + GRACE_PERIOD + HALF_LIFE * 50
    result = effective_mastery_for_review(0.9, updated_at=_UPDATED_AT, now=now)
    assert 0.0 < result < 0.0001


def test_deterministic_given_identical_inputs():
    now = _UPDATED_AT + GRACE_PERIOD + HALF_LIFE * 3
    results = {
        effective_mastery_for_review(0.75, updated_at=_UPDATED_AT, now=now) for _ in range(10)
    }
    assert len(results) == 1
