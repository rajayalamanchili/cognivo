"""Unit tests: per-topic weak-area classification boundaries
(FR-002, FR-003, FR-003a, FR-004), T008.

Pure-function tests, no DB -- `classify_topic_status` takes plain
mastery values, mirroring `test_mastery_bkt.py`'s own pure-function
convention for `mastery_band_for`.
"""

from src.services.recommendation.weak_area import (
    CONFIDENT_MIN_EVENTS,
    TopicStatus,
    classify_topic_status,
)


def test_no_mastery_state_row_is_not_yet_assessed():
    assert (
        classify_topic_status(p_mastery=None, update_count=0) is TopicStatus.NOT_YET_ASSESSED
    )


def test_fewer_than_three_events_is_insufficient_data():
    assert CONFIDENT_MIN_EVENTS == 3
    assert (
        classify_topic_status(p_mastery=0.1, update_count=1) is TopicStatus.INSUFFICIENT_DATA
    )
    assert (
        classify_topic_status(p_mastery=0.1, update_count=2) is TopicStatus.INSUFFICIENT_DATA
    )


def test_insufficient_data_applies_regardless_of_p_mastery():
    # A single wrong answer alone must never produce a confident weak
    # flag, even if the raw p_mastery already dipped into the
    # struggling band (spec.md Edge Cases).
    assert (
        classify_topic_status(p_mastery=0.05, update_count=1) is TopicStatus.INSUFFICIENT_DATA
    )


def test_exactly_three_events_is_confidently_assessed():
    assert classify_topic_status(p_mastery=0.1, update_count=3) is TopicStatus.WEAK


def test_struggling_band_below_0_4_is_weak():
    assert classify_topic_status(p_mastery=0.0, update_count=3) is TopicStatus.WEAK
    assert classify_topic_status(p_mastery=0.39999, update_count=3) is TopicStatus.WEAK


def test_developing_band_is_in_progress_not_weak():
    assert classify_topic_status(p_mastery=0.4, update_count=3) is TopicStatus.IN_PROGRESS
    assert classify_topic_status(p_mastery=0.69999, update_count=3) is TopicStatus.IN_PROGRESS


def test_mastered_band_requires_confirmation_streak():
    # Matches data-model.md's Mastered-confirmation rule -- a >=0.7
    # posterior without two consecutive confirming observations still
    # reads as "in progress" (developing), not "mastered".
    assert (
        classify_topic_status(p_mastery=0.75, update_count=3, consecutive_mastered_observations=0)
        is TopicStatus.IN_PROGRESS
    )
    assert (
        classify_topic_status(p_mastery=0.75, update_count=3, consecutive_mastered_observations=2)
        is TopicStatus.MASTERED
    )
