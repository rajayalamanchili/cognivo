"""Unit tests: the extracted `rank_eligible_topics` eligibility/ranking
helper (research.md §1), T017.

Pure-function tests against plain lookup maps, no DB -- mirrors
`test_weak_area_classification.py`'s convention for
`classify_topic_status`. Covers two things: (1) a regression check that
extracting this helper out of `select_next_topic` preserved its exact
chosen-topic behavior (same eligibility rule, same tie-break), and (2)
the new upcoming-topics slice `preview_topic_priority` wraps around it
-- up to 3 correctly-ranked entries, and the `is_fallback` flag when
zero topics are strictly eligible.
"""

from src.agents.sequencing.agent import rank_eligible_topics


def test_regression_matches_select_next_topics_existing_eligibility_rule():
    # Mirrors test_next_topic_eligibility.py's
    # test_topic_with_unsatisfied_prerequisite_is_not_eligible: no
    # MasteryState rows at all -- only the two zero-prerequisite topics
    # are eligible; a prerequisite-blocked topic never wins.
    ranked, is_fallback = rank_eligible_topics(
        ["integers-and-operations", "variables-and-expressions", "order-of-operations"],
        band_by_topic={
            "integers-and-operations": "unknown",
            "variables-and-expressions": "unknown",
            "order-of-operations": "unknown",
        },
        p_mastery_by_topic={
            "integers-and-operations": None,
            "variables-and-expressions": None,
            "order-of-operations": None,
        },
        prereqs_by_topic={
            "integers-and-operations": [],
            "variables-and-expressions": [],
            "order-of-operations": ["integers-and-operations"],
        },
    )
    assert ranked[0] in ("integers-and-operations", "variables-and-expressions")
    assert "order-of-operations" not in ranked
    assert is_fallback is False


def test_regression_unknown_ranked_ahead_of_any_numeric_p_mastery():
    # Mirrors test_next_topic_eligibility.py's
    # test_unknown_ranked_ahead_of_any_numeric_p_mastery.
    ranked, is_fallback = rank_eligible_topics(
        ["integers-and-operations", "variables-and-expressions"],
        band_by_topic={
            "integers-and-operations": "unknown",
            "variables-and-expressions": "unknown",
        },
        p_mastery_by_topic={"integers-and-operations": None, "variables-and-expressions": 0.01},
        prereqs_by_topic={"integers-and-operations": [], "variables-and-expressions": []},
    )
    assert ranked[0] == "integers-and-operations"
    assert is_fallback is False


def test_regression_fallback_selects_lowest_p_mastery_mastered_topic():
    # Mirrors test_next_topic_fallback.py's
    # test_fallback_selects_lowest_p_mastery_mastered_topic: every topic
    # mastered (nothing strictly eligible) falls back to the pool of
    # mastered topics, lowest p_mastery first.
    topic_ids = ["a", "b", "c"]
    ranked, is_fallback = rank_eligible_topics(
        topic_ids,
        band_by_topic={t: "mastered" for t in topic_ids},
        p_mastery_by_topic={"a": 0.9, "b": 0.71, "c": 0.95},
        prereqs_by_topic={t: [] for t in topic_ids},
    )
    assert ranked[0] == "b"
    assert is_fallback is True


def test_upcoming_topics_are_the_next_ranked_entries_after_the_chosen_one():
    topic_ids = ["a", "b", "c", "d", "e"]
    ranked, is_fallback = rank_eligible_topics(
        topic_ids,
        band_by_topic={t: "unknown" for t in topic_ids},
        p_mastery_by_topic={"a": None, "b": None, "c": None, "d": None, "e": None},
        prereqs_by_topic={t: [] for t in topic_ids},
    )
    assert is_fallback is False
    next_topic, upcoming = ranked[0], ranked[1:4]
    assert next_topic == "a"
    # Tie-broken by original list order -- b, c, d are the next 3, e is
    # excluded (SC-006: capped at 3).
    assert upcoming == ["b", "c", "d"]


def test_upcoming_topics_fewer_than_three_when_pool_is_smaller():
    topic_ids = ["a", "b"]
    ranked, _is_fallback = rank_eligible_topics(
        topic_ids,
        band_by_topic={"a": "unknown", "b": "unknown"},
        p_mastery_by_topic={"a": None, "b": None},
        prereqs_by_topic={"a": [], "b": []},
    )
    upcoming = ranked[1:4]
    assert upcoming == ["b"]


def test_is_fallback_true_when_zero_topics_strictly_eligible():
    # Every topic prerequisite-blocked (not mastered), so nothing is
    # strictly eligible and nothing is mastered either -- falls back to
    # the full topic pool.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "struggling", "b": "struggling"},
        p_mastery_by_topic={"a": 0.2, "b": 0.3},
        prereqs_by_topic={"a": ["b"], "b": ["a"]},
    )
    assert is_fallback is True
    assert set(ranked) == {"a", "b"}
