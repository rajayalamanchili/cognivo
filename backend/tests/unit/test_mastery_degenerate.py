"""Unit test: degenerate answer patterns don't yield a "mastered" band (SC-005).

A learner who always submits the same multiple-choice option regardless
of the question's actual content, or always submits the same numeric
value regardless of content, gets correct results only at the model's
own guess rate (p(G)=0.25 for multiple_choice, 0.05 for numeric) --
since content varies, which option/value is actually correct is
effectively uncorrelated with the learner's fixed choice.

For numeric questions specifically, a single correct answer is on its
own strong enough Bayesian evidence (p(G)=0.05) to spike p_mastery past
0.7 -- a real risk when that one correct answer was actually a lucky
guess. data-model.md's Mastered-confirmation rule (two consecutive
>=0.7 observations required, see src/models/enums.py) exists
specifically to stop that single coincidence from registering as
"mastered": the very next answer in a degenerate pattern reverts below
threshold, so confirmation never arrives.
"""

from src.models.enums import MasteryBand, QuestionType
from src.services.mastery.bkt import P_G_MULTIPLE_CHOICE, P_G_NUMERIC, apply_bkt_update


def _simulate_guess_rate_stream(question_type: QuestionType, guess_rate: float, n: int):
    """Apply n BKT updates where exactly `guess_rate` fraction land correct,
    evenly spaced -- the correctness pattern a fixed, content-blind answer
    choice would statistically produce. Returns the full observation
    history so tests can assert over every intermediate state, not just
    the final one (a transient spike right after a lucky guess is exactly
    what the confirmation-streak rule must catch)."""
    observation = None
    history = []
    hit_every = round(1 / guess_rate)
    for i in range(1, n + 1):
        correct = i % hit_every == 0
        observation = apply_bkt_update(observation, correct=correct, question_type=question_type)
        history.append(observation)
    return history


def test_fixed_multiple_choice_option_never_registers_mastered():
    history = _simulate_guess_rate_stream(QuestionType.MULTIPLE_CHOICE, P_G_MULTIPLE_CHOICE, n=40)
    assert all(observation.band != MasteryBand.MASTERED for observation in history)


def test_fixed_numeric_value_never_registers_mastered():
    history = _simulate_guess_rate_stream(QuestionType.NUMERIC, P_G_NUMERIC, n=60)
    # Without the confirmation-streak rule, trial 20 spikes p_mastery to
    # ~0.72 off a single lucky guess -- assert it does NOT read as
    # "mastered" at any point in the scripted pattern.
    assert all(observation.band != MasteryBand.MASTERED for observation in history)


def test_correct_rate_above_guess_rate_can_reach_mastered():
    # Sanity check the test methodology itself: a correctness rate
    # genuinely above the guess rate (i.e. real, sustained signal, not a
    # degenerate fixed-choice pattern) CAN cross into "mastered" once
    # confirmed -- confirms the two tests above are catching guess-rate
    # patterns specifically, not just "BKT never reaches mastered."
    observation = None
    for _ in range(20):
        observation = apply_bkt_update(
            observation, correct=True, question_type=QuestionType.MULTIPLE_CHOICE
        )
    assert observation.band == MasteryBand.MASTERED
