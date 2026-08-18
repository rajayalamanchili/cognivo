"""Unit tests: the streak-based in-quiz difficulty step function
(FR-002, FR-007, research.md §1), T007.

Pure-function tests against plain band/streak values, no DB -- mirrors
`test_mastery_bkt.py`'s/`test_weak_area_classification.py`'s own
pure-function convention.
"""

from src.models.enums import DifficultyBand
from src.services.quiz.difficulty import current_difficulty_for_topic, next_difficulty


def test_two_consecutive_correct_moves_up_one_band():
    step = next_difficulty(DifficultyBand.EASY, 1, correct=True)
    assert step.band == DifficultyBand.MEDIUM
    assert step.streak == 0
    assert step.streak_length_at_decision == 2
    assert step.held_at_bound is False


def test_two_consecutive_incorrect_moves_down_one_band():
    step = next_difficulty(DifficultyBand.MEDIUM, -1, correct=False)
    assert step.band == DifficultyBand.EASY
    assert step.streak == 0
    assert step.streak_length_at_decision == 2
    assert step.held_at_bound is False


def test_single_correct_answer_does_not_move_the_band_yet():
    step = next_difficulty(DifficultyBand.EASY, 0, correct=True)
    assert step.band == DifficultyBand.EASY
    assert step.streak == 1
    assert step.streak_length_at_decision == 1
    assert step.held_at_bound is False


def test_incorrect_answer_breaks_a_building_correct_streak_and_starts_fresh():
    # streak=1 (one correct so far), then an incorrect answer -- does not
    # average out to 0, it starts a fresh incorrect streak of length 1.
    step = next_difficulty(DifficultyBand.EASY, 1, correct=False)
    assert step.band == DifficultyBand.EASY
    assert step.streak == -1
    assert step.streak_length_at_decision == 1


def test_streak_resets_to_zero_every_time_the_band_changes():
    first = next_difficulty(DifficultyBand.EASY, 1, correct=True)
    assert first.band == DifficultyBand.MEDIUM
    assert first.streak == 0
    # A fresh two-answer streak is required again to move further.
    second = next_difficulty(first.band, first.streak, correct=True)
    assert second.band == DifficultyBand.MEDIUM
    assert second.streak == 1


def test_holds_at_hard_without_erroring_and_still_resets_the_streak():
    step = next_difficulty(DifficultyBand.HARD, 1, correct=True)
    assert step.band == DifficultyBand.HARD
    assert step.streak == 0
    assert step.streak_length_at_decision == 2
    assert step.held_at_bound is True


def test_holds_at_easy_without_erroring_and_still_resets_the_streak():
    step = next_difficulty(DifficultyBand.EASY, -1, correct=False)
    assert step.band == DifficultyBand.EASY
    assert step.streak == 0
    assert step.streak_length_at_decision == 2
    assert step.held_at_bound is True


def test_current_difficulty_for_topic_starts_at_easy_with_no_history():
    assert current_difficulty_for_topic([]) == DifficultyBand.EASY


def test_current_difficulty_for_topic_replays_full_history():
    # correct, correct -> moves to medium; correct, correct -> hard.
    history = [True, True, True, True]
    assert current_difficulty_for_topic(history) == DifficultyBand.HARD


def test_current_difficulty_for_topic_holds_at_hard_for_a_long_correct_run():
    history = [True] * 10
    assert current_difficulty_for_topic(history) == DifficultyBand.HARD


def test_current_difficulty_for_topic_holds_at_easy_for_a_long_incorrect_run():
    history = [False] * 10
    assert current_difficulty_for_topic(history) == DifficultyBand.EASY
