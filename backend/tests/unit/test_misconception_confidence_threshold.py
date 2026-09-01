"""Unit test: `classify.select_classification`'s confidence-threshold
gate withholds a classification when every candidate label's mean
probability is below `MISCONCEPTION_CONFIDENCE_THRESHOLD` (spec 013
FR-006, research.md §5) -- pure function, no DB/model/embedding call.
"""

from src.services.misconception.classify import select_classification


def test_below_confidence_threshold_withholds_classification():
    assert (
        select_classification(
            qualifying_event_count=5,
            mean_probability_by_id={"confuses-x-with-y": 0.4, "confuses-a-with-b": 0.3},
            confidence_threshold=0.6,
        )
        is None
    )


def test_at_confidence_threshold_classifies():
    result = select_classification(
        qualifying_event_count=5,
        mean_probability_by_id={"confuses-x-with-y": 0.6},
        confidence_threshold=0.6,
    )
    assert result is not None
    assert result.misconception_id == "confuses-x-with-y"


def test_picks_highest_probability_label_among_candidates():
    result = select_classification(
        qualifying_event_count=5,
        mean_probability_by_id={"confuses-x-with-y": 0.62, "confuses-a-with-b": 0.81},
        confidence_threshold=0.6,
    )
    assert result is not None
    assert result.misconception_id == "confuses-a-with-b"
    assert result.confidence == 0.81


def test_no_candidate_labels_withholds_classification():
    assert (
        select_classification(qualifying_event_count=5, mean_probability_by_id={})
        is None
    )
