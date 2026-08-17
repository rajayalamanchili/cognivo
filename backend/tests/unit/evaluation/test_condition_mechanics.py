"""Unit tests: simulated-answer draw rate and the mastered-band
convergence gate (research.md §3, §5; validates T005 -- conditions.py).
"""

import random
from unittest.mock import patch

from src.models.enums import QuestionType
from src.models.topic import Topic
from src.services.evaluation import conditions
from src.services.evaluation.conditions import (
    SimulatedAnswer,
    draw_simulated_answer,
    has_reached_mastered_band,
    run_fixed_order_condition,
)
from src.services.mastery.bkt import MasteryObservation


def _topic(
    preferred_type: str = "multiple_choice", topic_id: str = "topic-a", order_index: int = 0
) -> Topic:
    return Topic(
        subject_id="fake-subject",
        topic_id=topic_id,
        display_name=topic_id,
        is_entry_level=(order_index == 0),
        skill_definition={"skill": {"preferred_question_types": [preferred_type]}},
        order_index=order_index,
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


def test_fixed_order_visits_topics_in_order_index_order_and_recycles_unmastered():
    # Deliberately out-of-order_index input list -- proves the function
    # sorts by order_index itself, never trusting caller ordering.
    t2 = _topic(topic_id="t2", order_index=2, preferred_type="numeric")
    t0 = _topic(topic_id="t0", order_index=0, preferred_type="numeric")
    t1 = _topic(topic_id="t1", order_index=1, preferred_type="multiple_choice")
    topics = [t2, t0, t1]

    visited_order: list[str] = []
    # t0/t2 (numeric, always correct) master in exactly 2 questions each
    # -- fewer than the 3-question per-visit cap -- banking budget. t1's
    # first answer is deliberately wrong, so 3 always-correct answers
    # after it (its per-visit cap) leave it one question short of the
    # mastered band, needing a re-cycle to finish -- which the budget
    # t0/t2 banked makes possible within the shared total budget.
    scripted_first_wrong = {"t1": False}

    def fake_draw(topic, *, truly_mastered, rng):
        visited_order.append(topic.topic_id)
        correct = scripted_first_wrong.pop(topic.topic_id, True)
        preferred = topic.skill_definition["skill"]["preferred_question_types"][0]
        return SimulatedAnswer(
            topic_id=topic.topic_id, question_type=QuestionType(preferred), correct=correct
        )

    with patch.object(conditions, "draw_simulated_answer", side_effect=fake_draw):
        outcome = run_fixed_order_condition(
            topics,
            true_mastery={"t0": True, "t1": True, "t2": True},
            max_questions_per_topic=3,
            rng=random.Random(1),
        )

    assert outcome.converged is True
    assert outcome.questions_to_mastery == 8
    assert visited_order == ["t0", "t0", "t1", "t1", "t1", "t2", "t2", "t1"]
