"""Unit tests: `rank_eligible_topics`'s grade gate (spec 017 User Story
2, T023).

Pure-function tests against plain lookup maps, no DB -- mirrors
`test_topic_priority_ranking.py`'s convention for the same function's
pre-existing band/prerequisite eligibility rule. This file only covers
the new `grade_by_topic`/`unlocked_grade` gate; the band/prerequisite
rule itself stays covered by `test_topic_priority_ranking.py`.
"""

from src.agents.sequencing.agent import rank_eligible_topics


def test_topic_above_unlocked_grade_never_eligible_regardless_of_band_or_prereqs():
    # "b" is mastered with no prerequisites -- by band/prereq rules alone
    # it would win outright -- but its grade (7) is above unlocked_grade
    # (6), so it must never surface.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "unknown", "b": "mastered"},
        p_mastery_by_topic={"a": None, "b": 0.99},
        prereqs_by_topic={"a": [], "b": []},
        grade_by_topic={"a": 6, "b": 7},
        unlocked_grade=6,
    )
    assert "b" not in ranked
    assert ranked == ["a"]
    assert is_fallback is False


def test_ungraded_topic_unaffected_by_grade_gate():
    # grade is None (ungraded topic) even though unlocked_grade is set --
    # must not be excluded.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "unknown", "b": "unknown"},
        p_mastery_by_topic={"a": None, "b": None},
        prereqs_by_topic={"a": [], "b": []},
        grade_by_topic={"a": None, "b": 9},
        unlocked_grade=6,
    )
    assert set(ranked) == {"a"}
    assert is_fallback is False


def test_topic_at_or_below_unlocked_grade_behaves_exactly_as_today():
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "unknown", "b": "unknown"},
        p_mastery_by_topic={"a": None, "b": None},
        prereqs_by_topic={"a": [], "b": []},
        grade_by_topic={"a": 5, "b": 6},
        unlocked_grade=6,
    )
    assert set(ranked) == {"a", "b"}
    assert is_fallback is False


def test_grade_gating_and_prerequisite_gating_both_apply_independently():
    # "b" is within the unlocked grade but its prerequisite "a" (a lower
    # grade) is not yet mastered -- grade-gating alone does not make it
    # eligible; prerequisite-gating still applies too.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "struggling", "b": "unknown"},
        p_mastery_by_topic={"a": 0.2, "b": None},
        prereqs_by_topic={"a": [], "b": ["a"]},
        grade_by_topic={"a": 6, "b": 6},
        unlocked_grade=6,
    )
    assert "b" not in ranked
    assert ranked == ["a"]
    assert is_fallback is False


def test_missing_grade_progress_defaults_to_lowest_declared_grade():
    # Caller-resolved default (data-model.md's defensive default): a
    # graded subject with no GradeProgress row yet passes unlocked_grade
    # as the lowest declared grade -- every higher-grade topic is
    # ineligible.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b", "c"],
        band_by_topic={"a": "unknown", "b": "unknown", "c": "unknown"},
        p_mastery_by_topic={"a": None, "b": None, "c": None},
        prereqs_by_topic={"a": [], "b": [], "c": []},
        grade_by_topic={"a": 6, "b": 7, "c": 8},
        unlocked_grade=6,
    )
    assert ranked == ["a"]
    assert is_fallback is False


def test_grade_gate_also_applies_to_fallback_pool():
    # Every within-grade topic is already mastered (nothing strictly
    # eligible), so ranking falls back -- but a higher-grade topic must
    # still never appear in that fallback pool.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "mastered", "b": "mastered"},
        p_mastery_by_topic={"a": 0.9, "b": 0.99},
        prereqs_by_topic={"a": [], "b": []},
        grade_by_topic={"a": 6, "b": 7},
        unlocked_grade=6,
    )
    assert ranked == ["a"]
    assert is_fallback is True


def test_no_unlocked_grade_means_no_gate_applied():
    # unlocked_grade=None (ungraded subject, or caller opted out) -- the
    # grade gate is inert even if grade_by_topic has values.
    ranked, is_fallback = rank_eligible_topics(
        ["a", "b"],
        band_by_topic={"a": "unknown", "b": "unknown"},
        p_mastery_by_topic={"a": None, "b": None},
        prereqs_by_topic={"a": [], "b": []},
        grade_by_topic={"a": 6, "b": 9},
        unlocked_grade=None,
    )
    assert set(ranked) == {"a", "b"}
    assert is_fallback is False
