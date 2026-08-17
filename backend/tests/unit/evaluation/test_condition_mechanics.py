"""Unit tests: simulated-answer draw rate and the mastered-band
convergence gate (research.md §3, §5; validates T005 -- conditions.py).
"""

import random

from src.models.topic import Topic
from src.services.evaluation.conditions import draw_simulated_answer, has_reached_mastered_band
from src.services.mastery.bkt import MasteryObservation


def _topic(preferred_type: str = "multiple_choice") -> Topic:
    return Topic(
        subject_id="fake-subject",
        topic_id="topic-a",
        display_name="Topic A",
        is_entry_level=True,
        skill_definition={"skill": {"preferred_question_types": [preferred_type]}},
        order_index=0,
    )


def test_truly_mastered_answers_correct_at_one_minus_slip_rate():
    topic = _topic()
    rng = random.Random(1)
    draws = [
        draw_simulated_answer(topic, truly_mastered=True, rng=rng).correct for _ in range(5000)
    ]
    rate = sum(draws) / len(draws)
    assert abs(rate - 0.9) < 0.02  # P(correct) = 1 - P_S = 1 - 0.1


def test_not_mastered_answers_correct_at_guess_rate_multiple_choice():
    topic = _topic("multiple_choice")
    rng = random.Random(2)
    draws = [
        draw_simulated_answer(topic, truly_mastered=False, rng=rng).correct for _ in range(5000)
    ]
    rate = sum(draws) / len(draws)
    assert abs(rate - 0.25) < 0.02


def test_not_mastered_answers_correct_at_guess_rate_numeric():
    topic = _topic("numeric")
    rng = random.Random(3)
    draws = [
        draw_simulated_answer(topic, truly_mastered=False, rng=rng).correct for _ in range(5000)
    ]
    rate = sum(draws) / len(draws)
    assert abs(rate - 0.05) < 0.02


def test_answer_topic_and_question_type_are_preserved():
    topic = _topic("numeric")
    answer = draw_simulated_answer(topic, truly_mastered=True, rng=random.Random(4))
    assert answer.topic_id == "topic-a"
    assert answer.question_type.value == "numeric"


def test_convergence_requires_confirmation_streak_not_bare_threshold():
    # p_mastery >= 0.7 alone (a single high observation) must NOT count --
    # research.md §5 requires the real confirmation-streak-gated band.
    single_high_observation = MasteryObservation(
        p_mastery=0.75, consecutive_mastered_observations=1
    )
    assert has_reached_mastered_band(single_high_observation) is False

    confirmed = MasteryObservation(p_mastery=0.75, consecutive_mastered_observations=2)
    assert has_reached_mastered_band(confirmed) is True


def test_convergence_false_for_no_observation_yet():
    assert has_reached_mastered_band(None) is False


def test_convergence_false_below_mastered_band_even_with_long_streak():
    developing_despite_streak = MasteryObservation(
        p_mastery=0.5, consecutive_mastered_observations=5
    )
    assert has_reached_mastered_band(developing_despite_streak) is False
