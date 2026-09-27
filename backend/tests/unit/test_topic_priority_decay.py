"""Unit tests: `rank_eligible_topics`'s decay-aware sort of the
mastered-topic fallback pool (research.md §2, FR-003/FR-004/FR-012).

Pure-function tests against plain lookup maps, no DB -- mirrors
`test_sequencing.py`'s grade-gate convention for the same function.
This file only covers the new `updated_at_by_topic`/`now` kwargs; the
pre-existing band/prerequisite/grade rules stay covered by
`test_topic_priority_ranking.py`/`test_sequencing.py`.
"""

import datetime

from src.agents.sequencing.agent import rank_eligible_topics
from src.services.mastery.decay import GRACE_PERIOD, HALF_LIFE

_NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def test_more_decayed_mastered_topic_ranks_first_in_fallback():
    # Equal raw p_mastery -- only "a"'s far-older updated_at should
    # decide the ordering.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "mastered", "b": "mastered"},
        p_mastery_by_topic={"a": 0.8, "b": 0.8},
        prereqs_by_topic={"a": [], "b": []},
        updated_at_by_topic={
            "a": _NOW - GRACE_PERIOD - HALF_LIFE * 3,
            "b": _NOW - datetime.timedelta(days=1),
        },
        now=_NOW,
    )
    assert ranked == ["a", "b"]
    assert is_fallback is True


def test_within_grace_period_matches_omitting_new_kwargs():
    band_by_topic = {"a": "mastered", "b": "mastered"}
    p_mastery_by_topic = {"a": 0.75, "b": 0.9}
    prereqs_by_topic = {"a": [], "b": []}

    with_kwargs, _ = rank_eligible_topics(
        ["a", "b"],
        band_by_topic=band_by_topic,
        p_mastery_by_topic=p_mastery_by_topic,
        prereqs_by_topic=prereqs_by_topic,
        updated_at_by_topic={"a": _NOW - datetime.timedelta(days=1), "b": _NOW},
        now=_NOW,
    )
    without_kwargs, _ = rank_eligible_topics(
        ["a", "b"],
        band_by_topic=band_by_topic,
        p_mastery_by_topic=p_mastery_by_topic,
        prereqs_by_topic=prereqs_by_topic,
    )
    assert with_kwargs == without_kwargs == ["a", "b"]


def test_eligible_pool_unaffected_by_a_mastered_topics_decay():
    # "b" is mastered and heavily decayed, but with "a" (unknown, prereqs
    # satisfied) eligible, the eligible pool -- not the fallback -- wins,
    # and its ordering must ignore "b"'s decay entirely.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "unknown", "b": "mastered"},
        p_mastery_by_topic={"a": None, "b": 0.99},
        prereqs_by_topic={"a": [], "b": []},
        updated_at_by_topic={"b": _NOW - GRACE_PERIOD - HALF_LIFE * 100},
        now=_NOW,
    )
    assert ranked == ["a"]
    assert is_fallback is False


def test_tie_in_effective_mastery_breaks_by_order_index():
    # "a" and "b" have different raw p_mastery/updated_at but are chosen
    # so their decayed effective mastery ties exactly -- the existing
    # order_index tie-break (list position) must still decide it.
    elapsed_a = GRACE_PERIOD + HALF_LIFE
    updated_at_a = _NOW - elapsed_a
    # b's raw p_mastery is half of a's, decayed by exactly one extra
    # half-life less -- so both land on the same effective value.
    updated_at_b = _NOW - GRACE_PERIOD
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "mastered", "b": "mastered"},
        p_mastery_by_topic={"a": 0.8, "b": 0.4},
        prereqs_by_topic={"a": [], "b": []},
        updated_at_by_topic={"a": updated_at_a, "b": updated_at_b},
        now=_NOW,
    )
    assert is_fallback is True
    assert ranked == ["a", "b"]
