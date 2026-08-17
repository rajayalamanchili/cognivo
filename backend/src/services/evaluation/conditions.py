"""Shared simulation machinery for every ordering condition (research.md §3-§7).

The Sequencing Agent condition is the only one that touches the
database -- it must exercise the real `select_next_topic` code path,
which reads/writes real Postgres rows keyed to a real `DemoLearnerProfile`
(research.md §6). The random and fixed-order baselines run entirely
in-memory (research.md §4) and only need the answer-draw/convergence
helpers below, which every condition shares.
"""

import contextlib
import random
import uuid
from collections.abc import Generator
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.agents.diagnostic.agent import preferred_question_type
from src.agents.sequencing.agent import NextTopicSelection
from src.models.assessment_event import AssessmentEvent
from src.models.demo_learner_profile import DemoLearnerProfile
from src.models.enums import AssessmentEventType, MasteryBand, QuestionType
from src.models.mastery_state import MasteryState
from src.models.topic import Topic
from src.services.audit_log.writer import record_event
from src.services.mastery.bkt import P_S, MasteryObservation, guess_probability

# Constitution Principle VIII: every synthetic learner this harness
# creates is identifiable by this prefix, in addition to `is_demo=True`.
EVAL_HARNESS_LEARNER_PREFIX = "eval-harness-"


@dataclass(frozen=True)
class SimulatedAnswer:
    """One synthetic answer, generated on demand during a condition's
    run loop (data-model.md's `SimulatedAnswer`)."""

    topic_id: str
    question_type: QuestionType
    correct: bool


def draw_simulated_answer(
    topic: Topic, *, truly_mastered: bool, rng: random.Random
) -> SimulatedAnswer:
    """One Bernoulli-drawn simulated answer for `topic`, using the same
    locked BKT emission parameters and `preferred_question_type` helper
    production uses (research.md §3): `P(correct) = 1 - P_S` if the
    topic's latent ground truth is truly mastered, else
    `guess_probability(question_type)`."""
    question_type = preferred_question_type(topic)
    p_correct = (1 - P_S) if truly_mastered else guess_probability(question_type)
    return SimulatedAnswer(
        topic_id=topic.topic_id,
        question_type=question_type,
        correct=rng.random() < p_correct,
    )


def has_reached_mastered_band(observation: MasteryObservation | None) -> bool:
    """Convergence check: has this topic reached the real,
    confirmation-streak-gated `mastered` band (research.md §5), via
    `MasteryObservation.band` -- which itself wraps `mastery_band_for` --
    never a bare `p_mastery >= 0.7` shortcut."""
    return observation is not None and observation.band == MasteryBand.MASTERED


@contextlib.contextmanager
def synthetic_learners(
    db: Session, *, count: int
) -> Generator[list[DemoLearnerProfile], None, None]:
    """Creates `count` `is_demo=True` `DemoLearnerProfile` rows
    (`eval-harness-`-prefixed, Constitution Principle VIII) for the
    Sequencing Agent condition to use, and guarantees every row this run
    creates against them -- `MasteryState` and `AssessmentEvent` rows
    included -- is deleted at the end, success or failure (research.md
    §6-§7)."""
    learners = [
        DemoLearnerProfile(
            display_name=f"{EVAL_HARNESS_LEARNER_PREFIX}{uuid.uuid4()}", is_demo=True
        )
        for _ in range(count)
    ]
    db.add_all(learners)
    db.flush()
    try:
        yield learners
    finally:
        db.rollback()
        learner_ids = [learner.learner_id for learner in learners]
        db.query(AssessmentEvent).filter(AssessmentEvent.learner_id.in_(learner_ids)).delete(
            synchronize_session=False
        )
        db.query(MasteryState).filter(MasteryState.learner_id.in_(learner_ids)).delete(
            synchronize_session=False
        )
        db.query(DemoLearnerProfile).filter(DemoLearnerProfile.learner_id.in_(learner_ids)).delete(
            synchronize_session=False
        )
        db.commit()


def record_topic_selection_event(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, selection: NextTopicSelection
) -> AssessmentEvent:
    """Writes one `NEXT_TOPIC_SELECTED` `AssessmentEvent` row per
    Sequencing Agent condition decision -- the same payload shape and
    write path (`record_event`) `questions.py`'s real route uses
    (FR-014; research.md §7), so this condition's audit trail is
    genuinely real, not a stand-in. `question_id` is left `None`: the
    harness never generates a real `GeneratedQuestion` row (research.md
    §1)."""
    return record_event(
        db,
        learner_id=learner_id,
        event_type=AssessmentEventType.NEXT_TOPIC_SELECTED,
        subject_id=subject_id,
        topic_id=selection.topic_id,
        payload={
            "candidate_topics_considered": [
                {
                    "topic_id": candidate.topic_id,
                    "band": candidate.band,
                    "p_mastery": candidate.p_mastery,
                }
                for candidate in selection.candidates_considered
            ],
            "chosen_topic": selection.topic_id,
            "chosen_topic_band": selection.band,
            "chosen_topic_p_mastery": selection.p_mastery,
            "is_fallback": selection.is_fallback,
        },
    )
