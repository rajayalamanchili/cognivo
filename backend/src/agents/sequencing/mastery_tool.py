"""Sequencing Agent's mastery-update tool (FR-004, FR-005).

The only place a `MasteryState` row is created or updated. Wraps the
pure BKT function (services/mastery/bkt.py) with the DB read-modify-
write -- Constitution Principle I: mastery state comes from this
explicit, deterministic model, called as a tool, never re-derived from
an LLM's impression of the conversation.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.enums import MasteryBand, QuestionType
from src.models.mastery_state import MasteryState
from src.services.mastery.bkt import (
    P_L0,
    P_S,
    P_T,
    MasteryObservation,
    apply_bkt_update,
    guess_probability,
)


@dataclass(frozen=True)
class MasteryUpdateResult:
    prior_p_mastery: float | None  # None if this topic had no prior MasteryState row (FR-005)
    posterior_p_mastery: float
    posterior_band: MasteryBand
    update_count: int
    bkt_params_used: dict[str, float]


def apply_mastery_update(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    topic_id: str,
    correct: bool,
    question_type: QuestionType,
) -> MasteryUpdateResult:
    """Reads any existing MasteryState row, applies one BKT update, and
    writes the result back -- insert on a topic's first answer, update
    in place afterward (data-model.md's State-transition rule). Does not
    commit; callers control the transaction so this can be written
    atomically alongside the AssessmentEvent row that documents it."""
    existing = db.get(MasteryState, (learner_id, subject_id, topic_id))

    prior_observation: MasteryObservation | None = None
    if existing is not None:
        prior_observation = MasteryObservation(
            p_mastery=existing.p_mastery,
            consecutive_mastered_observations=existing.consecutive_mastered_observations,
        )

    posterior = apply_bkt_update(prior_observation, correct=correct, question_type=question_type)

    if existing is None:
        existing = MasteryState(
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            p_mastery=posterior.p_mastery,
            update_count=1,
            consecutive_mastered_observations=posterior.consecutive_mastered_observations,
        )
        db.add(existing)
    else:
        existing.p_mastery = posterior.p_mastery
        existing.update_count += 1
        existing.consecutive_mastered_observations = posterior.consecutive_mastered_observations

    db.flush()

    return MasteryUpdateResult(
        prior_p_mastery=prior_observation.p_mastery if prior_observation else None,
        posterior_p_mastery=posterior.p_mastery,
        posterior_band=posterior.band,
        update_count=existing.update_count,
        bkt_params_used={
            "p_l0": P_L0,
            "p_t": P_T,
            "p_s": P_S,
            "p_g": guess_probability(question_type),
        },
    )
