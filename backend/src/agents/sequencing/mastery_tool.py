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
from src.models.grade_band import GradeBand
from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState
from src.models.topic import Topic
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
    grade_unlocked: int | None = None  # non-null only on the update that unlocks a next grade


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

    grade_unlocked = _maybe_unlock_next_grade(
        db,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        posterior_band=posterior.band,
    )

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
        grade_unlocked=grade_unlocked,
    )


def _maybe_unlock_next_grade(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    topic_id: str,
    posterior_band: MasteryBand,
) -> int | None:
    """FR-004: on a topic reaching `mastered` whose grade equals the
    learner's current `unlocked_grade`, advance `GradeProgress` to the
    next declared grade once every topic in the current grade is also
    mastered. `None` in every other case (data-model.md's
    `MasteryUpdateResult.grade_unlocked` contract): ungraded topic, no
    `GradeProgress` row yet, the completing topic isn't the learner's
    current grade, the grade isn't fully mastered yet, or there's no
    next declared grade to unlock. `unlocked_grade` only ever increases
    here -- a regression (`posterior_band != MASTERED`) never reaches
    this far, so an already-unlocked grade can never be revoked (spec.md
    Edge Case)."""
    if posterior_band != MasteryBand.MASTERED:
        return None

    topic = db.get(Topic, (subject_id, topic_id))
    if topic.grade is None:
        return None

    progress = db.get(GradeProgress, (learner_id, subject_id))
    if progress is None or topic.grade != progress.unlocked_grade:
        return None

    grade_topic_ids = [
        t.topic_id
        for t in db.query(Topic)
        .filter(Topic.subject_id == subject_id, Topic.grade == progress.unlocked_grade)
        .all()
    ]
    mastery_by_topic = {
        state.topic_id: state
        for state in db.query(MasteryState)
        .filter(
            MasteryState.learner_id == learner_id,
            MasteryState.subject_id == subject_id,
            MasteryState.topic_id.in_(grade_topic_ids),
        )
        .all()
    }
    grade_fully_mastered = all(
        mastery_by_topic.get(t) is not None and mastery_by_topic[t].band == MasteryBand.MASTERED
        for t in grade_topic_ids
    )
    if not grade_fully_mastered:
        return None

    declared_grades = [
        row.grade for row in db.query(GradeBand).filter(GradeBand.subject_id == subject_id).all()
    ]
    higher_grades = [g for g in declared_grades if g > progress.unlocked_grade]
    if not higher_grades:
        return None

    next_grade = min(higher_grades)
    progress.unlocked_grade = next_grade
    db.flush()
    return next_grade
