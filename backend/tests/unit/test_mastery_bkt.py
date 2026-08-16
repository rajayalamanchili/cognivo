"""Unit tests: BKT update determinism and three-band boundaries (SC-001, T025).

Global BKT parameters per research.md §1: p(L0)=0.3, p(T)=0.1, p(S)=0.1,
p(G)=0.25 (multiple_choice) / 0.05 (numeric). "Mastered" additionally
requires two consecutive >=0.7 observations (data-model.md's Mastered-
confirmation rule, added to close the SC-005 gap where a single lucky
numeric guess could otherwise spike a topic straight to "mastered" --
see test_mastery_degenerate.py).
"""

from src.models.enums import MasteryBand, QuestionType, mastery_band_for
from src.services.mastery.bkt import MasteryObservation, apply_bkt_update


def test_update_is_pure_and_deterministic():
    results = {
        apply_bkt_update(None, correct=True, question_type=QuestionType.MULTIPLE_CHOICE)
        for _ in range(10)
    }
    assert len(results) == 1


def test_repeated_sequence_is_byte_identical():
    def run_sequence() -> MasteryObservation:
        observation = None
        for correct in [True, False, True, True, False, True, True, True, False, True]:
            observation = apply_bkt_update(
                observation, correct=correct, question_type=QuestionType.NUMERIC
            )
        return observation

    runs = [run_sequence() for _ in range(10)]
    assert len(set(runs)) == 1


def test_first_observation_uses_p_l0_as_prior():
    from_none = apply_bkt_update(None, correct=True, question_type=QuestionType.MULTIPLE_CHOICE)
    from_explicit_prior = apply_bkt_update(
        MasteryObservation(p_mastery=0.3, consecutive_mastered_observations=0),
        correct=True,
        question_type=QuestionType.MULTIPLE_CHOICE,
    )
    assert from_none == from_explicit_prior


def test_correct_answer_increases_mastery():
    observation = apply_bkt_update(None, correct=True, question_type=QuestionType.MULTIPLE_CHOICE)
    assert observation.p_mastery > 0.3


def test_incorrect_answer_decreases_mastery():
    observation = apply_bkt_update(None, correct=False, question_type=QuestionType.MULTIPLE_CHOICE)
    assert observation.p_mastery < 0.3


def test_posterior_always_in_unit_interval():
    observation = None
    for _ in range(50):
        observation = apply_bkt_update(
            observation, correct=True, question_type=QuestionType.MULTIPLE_CHOICE
        )
        assert 0.0 <= observation.p_mastery <= 1.0
    for _ in range(50):
        observation = apply_bkt_update(
            observation, correct=False, question_type=QuestionType.NUMERIC
        )
        assert 0.0 <= observation.p_mastery <= 1.0


def test_three_band_boundaries():
    # consecutive_mastered_observations >= 2 -- confirmation already satisfied,
    # so these isolate the raw 0.4/0.7 numeric boundaries.
    assert mastery_band_for(0.0, 2) == MasteryBand.STRUGGLING
    assert mastery_band_for(0.39999, 2) == MasteryBand.STRUGGLING
    assert mastery_band_for(0.4, 2) == MasteryBand.DEVELOPING
    assert mastery_band_for(0.69999, 2) == MasteryBand.DEVELOPING
    assert mastery_band_for(0.7, 2) == MasteryBand.MASTERED
    assert mastery_band_for(1.0, 2) == MasteryBand.MASTERED


def test_mastered_requires_confirmation_streak():
    # p_mastery alone crossing 0.7 is not sufficient without two
    # consecutive observations at/above threshold.
    assert mastery_band_for(0.75, 0) == MasteryBand.DEVELOPING
    assert mastery_band_for(0.75, 1) == MasteryBand.DEVELOPING
    assert mastery_band_for(0.75, 2) == MasteryBand.MASTERED


def test_sustained_correct_answers_eventually_reach_mastered():
    observation = None
    for _ in range(20):
        observation = apply_bkt_update(
            observation, correct=True, question_type=QuestionType.MULTIPLE_CHOICE
        )
    assert observation.band == MasteryBand.MASTERED


def test_sustained_incorrect_answers_stay_struggling():
    observation = None
    for _ in range(20):
        observation = apply_bkt_update(
            observation, correct=False, question_type=QuestionType.MULTIPLE_CHOICE
        )
    assert observation.band == MasteryBand.STRUGGLING


def test_confirmation_streak_resets_on_drop_below_threshold():
    observation = None
    for _ in range(20):
        observation = apply_bkt_update(
            observation, correct=True, question_type=QuestionType.MULTIPLE_CHOICE
        )
    assert observation.consecutive_mastered_observations >= 2

    observation = apply_bkt_update(observation, correct=False, question_type=QuestionType.NUMERIC)
    if observation.p_mastery < 0.7:
        assert observation.consecutive_mastered_observations == 0
