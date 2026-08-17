"""Unit tests: FR-007's prerequisite-chain recursion, T013.

Pure-function tests against plain lookup maps, no DB -- mirrors
test_weak_area_classification.py's convention for
`classify_topic_status`.
"""

from src.services.recommendation.next_step import NextStepReason, classify_prerequisite_gap

DISPLAY_NAMES = {
    "weak1": "Weak Topic",
    "gap1": "Gap Topic",
    "gapA": "Gap A",
    "gapB": "Gap B",
    "root1": "Root Cause",
    "mastered1": "Mastered Topic",
    "unknown1": "Unknown Topic",
}


def _classify(topic_id, *, prereqs, p_mastery, order_index=None):
    order_index = order_index or {t: i for i, t in enumerate(DISPLAY_NAMES)}
    return classify_prerequisite_gap(
        topic_id,
        prereqs_by_topic=prereqs,
        p_mastery_by_topic=p_mastery,
        order_index_by_topic=order_index,
        display_name_by_topic=DISPLAY_NAMES,
    )


def test_direct_practice_when_prerequisite_is_mastered():
    result = _classify(
        "weak1",
        prereqs={"weak1": ["mastered1"]},
        p_mastery={"weak1": 0.2, "mastered1": 0.8},
    )
    assert result.reason is NextStepReason.DIRECT_PRACTICE
    assert result.recommended_topic_id == "weak1"
    assert result.prerequisite_chain == []


def test_direct_practice_when_no_prerequisites_at_all():
    result = _classify("weak1", prereqs={"weak1": []}, p_mastery={"weak1": 0.2})
    assert result.reason is NextStepReason.DIRECT_PRACTICE
    assert result.recommended_topic_id == "weak1"


def test_single_level_prerequisite_gap():
    result = _classify(
        "weak1",
        prereqs={"weak1": ["gap1"], "gap1": []},
        p_mastery={"weak1": 0.2, "gap1": 0.1},
    )
    assert result.reason is NextStepReason.PREREQUISITE_GAP
    assert result.recommended_topic_id == "gap1"
    assert result.prerequisite_chain == ["gap1"]


def test_recurses_to_the_deepest_unmastered_root_cause():
    result = _classify(
        "weak1",
        prereqs={"weak1": ["gap1"], "gap1": ["root1"], "root1": []},
        p_mastery={"weak1": 0.2, "gap1": 0.1, "root1": 0.05},
    )
    assert result.reason is NextStepReason.PREREQUISITE_GAP
    assert result.recommended_topic_id == "root1"
    assert result.prerequisite_chain == ["gap1", "root1"]


def test_stops_at_a_prerequisite_with_no_recorded_data():
    result = _classify(
        "weak1",
        prereqs={"weak1": ["unknown1"], "unknown1": ["root1"], "root1": []},
        p_mastery={"weak1": 0.2, "unknown1": None, "root1": 0.05},
    )
    assert result.reason is NextStepReason.PREREQUISITE_NOT_YET_ASSESSED
    assert result.recommended_topic_id == "unknown1"
    # Recursion must not continue past the not-yet-assessed topic, even
    # though it has its own struggling prerequisite.
    assert result.prerequisite_chain == ["unknown1"]


def test_multiple_unmastered_prerequisites_picks_lowest_mastery():
    result = _classify(
        "weak1",
        prereqs={"weak1": ["gapA", "gapB"], "gapA": [], "gapB": []},
        p_mastery={"weak1": 0.2, "gapA": 0.35, "gapB": 0.1},
    )
    assert result.reason is NextStepReason.PREREQUISITE_GAP
    assert result.recommended_topic_id == "gapB"


def test_multiple_unmastered_prerequisites_tie_broken_by_order_index():
    result = _classify(
        "weak1",
        prereqs={"weak1": ["gapA", "gapB"], "gapA": [], "gapB": []},
        p_mastery={"weak1": 0.2, "gapA": 0.1, "gapB": 0.1},
        order_index={"weak1": 0, "gapA": 5, "gapB": 2},
    )
    assert result.reason is NextStepReason.PREREQUISITE_GAP
    assert result.recommended_topic_id == "gapB"


def test_developing_band_prerequisite_is_not_treated_as_unmastered():
    # FR-007's "unmastered" is the same struggling (<0.4) cutoff FR-002
    # uses -- a developing-band (0.4-0.7) prerequisite does not block.
    result = _classify(
        "weak1",
        prereqs={"weak1": ["developing1"]},
        p_mastery={"weak1": 0.2, "developing1": 0.5},
    )
    assert result.reason is NextStepReason.DIRECT_PRACTICE
