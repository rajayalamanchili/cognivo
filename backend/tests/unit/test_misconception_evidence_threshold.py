"""Unit test: `classify.select_classification`'s evidence-threshold
gate withholds a classification below `CONFIDENT_MIN_EVENTS` (3)
qualifying free-text incorrect events (spec 013 FR-005, research.md
§5) -- pure function, no DB/model/embedding call, mirroring
`weak_area.py`'s `classify_topic_status` unit tests.
"""

from src.services.misconception.classify import select_classification


def test_below_minimum_evidence_withholds_classification():
    assert (
        select_classification(
            qualifying_event_count=2,
            mean_probability_by_id={"confuses-x-with-y": 0.95},
        )
        is None
    )


def test_at_minimum_evidence_with_high_confidence_classifies():
    result = select_classification(
        qualifying_event_count=3,
        mean_probability_by_id={"confuses-x-with-y": 0.95},
    )
    assert result is not None
    assert result.misconception_id == "confuses-x-with-y"
    assert result.confidence == 0.95


def test_zero_qualifying_events_withholds_classification():
    assert (
        select_classification(qualifying_event_count=0, mean_probability_by_id={})
        is None
    )
