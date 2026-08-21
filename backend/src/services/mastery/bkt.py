"""Bayesian Knowledge Tracing mastery model (research.md §1, Constitution Principle I).

Fixed global parameters, not per-topic-fitted -- see research.md §1's
rationale (no real learner data exists yet to fit against, Constitution
Principle VIII). This is the ONLY place mastery is computed; the
Sequencing Agent calls `apply_bkt_update` as a tool rather than an LLM
ever guessing a mastery value from conversation context.
"""

from dataclasses import dataclass

from src.models.enums import MasteryBand, QuestionType, mastery_band_for

P_L0 = 0.3  # prior probability of mastery before any evidence
P_T = 0.1  # probability of transitioning not-mastered -> mastered per opportunity
P_S = 0.1  # slip: probability of an incorrect answer despite mastery
P_G_MULTIPLE_CHOICE = 0.25  # guess: probability of a correct answer despite no mastery
P_G_NUMERIC = 0.05
# Same rationale as numeric: no discrete option set to luck into, and
# rubric-based grading (spec 007) requires satisfying specific criteria
# rather than matching one exact value -- negligible blind-guess odds.
P_G_FREE_TEXT = 0.05


@dataclass(frozen=True)
class MasteryObservation:
    """One (learner, topic) pair's persisted BKT state -- mirrors the
    fields `MasteryState` stores, independent of the ORM layer so this
    module stays pure and DB-free."""

    p_mastery: float
    consecutive_mastered_observations: int

    @property
    def band(self) -> MasteryBand:
        return mastery_band_for(self.p_mastery, self.consecutive_mastered_observations)


def guess_probability(question_type: QuestionType) -> float:
    if question_type == QuestionType.MULTIPLE_CHOICE:
        return P_G_MULTIPLE_CHOICE
    if question_type == QuestionType.NUMERIC:
        return P_G_NUMERIC
    if question_type == QuestionType.FREE_TEXT:
        return P_G_FREE_TEXT
    raise ValueError(f"unknown question_type: {question_type!r}")


def apply_bkt_update(
    prior: MasteryObservation | None,
    *,
    correct: bool,
    question_type: QuestionType,
) -> MasteryObservation:
    """Returns the BKT posterior mastery state after one observation.

    `prior` is `None` for a topic's first observation, in which case
    `P_L0` is used as the prior (FR-005: "unknown" is the absence of a
    MasteryState row, never `P_L0` stored as a value) and the
    confirmation streak starts at zero. Every subsequent call passes the
    previous `MasteryObservation` as `prior`. Pure and deterministic:
    identical inputs always produce an identical output (SC-001).
    """
    prior_p = P_L0 if prior is None else prior.p_mastery
    prior_streak = 0 if prior is None else prior.consecutive_mastered_observations
    guess = guess_probability(question_type)

    if correct:
        numerator = prior_p * (1 - P_S)
        denominator = numerator + (1 - prior_p) * guess
    else:
        numerator = prior_p * P_S
        denominator = numerator + (1 - prior_p) * (1 - guess)

    posterior_given_evidence = numerator / denominator
    posterior = posterior_given_evidence + (1 - posterior_given_evidence) * P_T
    posterior = min(1.0, max(0.0, posterior))

    streak = prior_streak + 1 if posterior >= 0.7 else 0
    return MasteryObservation(p_mastery=posterior, consecutive_mastered_observations=streak)
