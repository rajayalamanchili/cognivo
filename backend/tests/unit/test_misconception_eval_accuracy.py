"""Unit test: `check_misconception_classifier_eval.py`'s
`compute_accuracy` returns the correct percentage given a known set of
predictions vs. expected labels, including the "classifier scores
lower than baseline" case (spec 013 Acceptance Scenario 2), T029.

Pure function, no DB/model/LLM call.
"""

from scripts.check_misconception_classifier_eval import compute_accuracy


def test_empty_input_returns_zero():
    assert compute_accuracy([]) == 0.0


def test_all_correct_returns_one():
    pairs = [("a", "a"), ("b", "b"), ("none", "none")]
    assert compute_accuracy(pairs) == 1.0


def test_all_wrong_returns_zero():
    pairs = [("a", "b"), ("b", "a")]
    assert compute_accuracy(pairs) == 0.0


def test_partial_match_returns_exact_fraction():
    pairs = [("a", "a"), ("b", "a"), ("c", "c"), ("none", "d")]
    assert compute_accuracy(pairs) == 0.5


def test_classifier_scoring_lower_than_baseline_is_reported_as_is():
    """spec 013 Acceptance Scenario 2: the helper itself does no
    gating/hiding -- it's the same function computing both numbers, so
    a lower classifier score is just a lower number, never suppressed."""
    classifier_pairs = [("a", "b"), ("a", "b"), ("b", "b")]
    baseline_pairs = [("a", "a"), ("a", "a"), ("b", "b")]

    classifier_accuracy = compute_accuracy(classifier_pairs)
    baseline_accuracy = compute_accuracy(baseline_pairs)

    assert classifier_accuracy < baseline_accuracy
    assert classifier_accuracy == 1 / 3
    assert baseline_accuracy == 1.0
