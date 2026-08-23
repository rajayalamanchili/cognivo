"""Shared simulation machinery for every ordering condition (research.md §3-§7).

The Sequencing Agent condition is the only one that touches the
database -- it must exercise the real `select_next_topic` code path,
which reads/writes real Postgres rows keyed to a real `LearnerProfile`
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
from src.agents.sequencing.agent import NextTopicSelection, select_next_topic
from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, MasteryBand, QuestionType
from src.models.learner_profile import LearnerProfile
from src.models.mastery_state import MasteryState
from src.models.topic import Topic
from src.services.audit_log.writer import record_event
from src.services.mastery.bkt import P_S, MasteryObservation, apply_bkt_update, guess_probability

# Constitution Principle VIII: every synthetic learner this harness
# creates is identifiable by this prefix, in addition to `is_demo=True`.
EVAL_HARNESS_LEARNER_PREFIX = "eval-harness-"


def _true_topic_ids(true_mastery: dict[str, bool]) -> frozenset[str]:
    """Topics this learner can genuinely converge on (FR-004; Clarifications,
    session 2026-08-17). BKT's transition probability means any topic
    -- including a genuinely-unmastered one -- eventually drifts toward
    the mastered band from guessing noise alone, so convergence is
    scoped to ground-truth-`true` topics only; a `false` topic reaching
    "mastered" would be spurious drift, not real mastery, and requiring
    it would make whole-learner convergence practically unreachable."""
    return frozenset(topic_id for topic_id, is_true in true_mastery.items() if is_true)


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
def synthetic_learners(db: Session, *, count: int) -> Generator[list[LearnerProfile], None, None]:
    """Creates `count` `is_demo=True` `LearnerProfile` rows
    (`eval-harness-`-prefixed, Constitution Principle VIII) for the
    Sequencing Agent condition to use, and guarantees every row this run
    creates against them -- `MasteryState` and `AssessmentEvent` rows
    included -- is deleted at the end, success or failure (research.md
    §6-§7)."""
    learners = [
        LearnerProfile(display_name=f"{EVAL_HARNESS_LEARNER_PREFIX}{uuid.uuid4()}", is_demo=True)
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
        db.query(LearnerProfile).filter(LearnerProfile.learner_id.in_(learner_ids)).delete(
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


@dataclass(frozen=True)
class LearnerOutcome:
    """One simulated learner's result under one ordering condition --
    the count of questions answered until every topic in the subject
    reached the mastered band, or `None` if the budget ran out first
    (FR-004)."""

    questions_to_mastery: int | None
    converged: bool


def run_sequencing_condition(
    db: Session,
    *,
    subject_id: str,
    topics: list[Topic],
    true_mastery: dict[str, bool],
    max_questions_per_topic: int,
    rng: random.Random,
) -> LearnerOutcome:
    """Runs the Sequencing Agent condition for one simulated learner: seeds
    a real synthetic learner (`synthetic_learners`), then loops calling
    the real `select_next_topic` + `apply_mastery_update` -- writing one
    real `AssessmentEvent` per decision (FR-014) -- until every topic
    this learner can genuinely master (`_true_topic_ids`) reaches the
    mastered band, or the budget (`max_questions_per_topic` per topic)
    is exhausted. `select_next_topic` has no access to ground truth, so
    it may still spend some of its budget on `false` topics exactly as
    a real request would -- only the convergence check is scoped
    (FR-004; Clarifications, session 2026-08-17). The synthetic learner
    and every row written against it are deleted before this returns,
    success or failure (research.md §6-§7)."""
    true_topic_ids = _true_topic_ids(true_mastery)
    if not true_topic_ids:
        return LearnerOutcome(questions_to_mastery=0, converged=True)

    budget = max_questions_per_topic * len(topics)
    topics_by_id = {topic.topic_id: topic for topic in topics}

    with synthetic_learners(db, count=1) as learners:
        learner = learners[0]
        mastered_topic_ids: set[str] = set()
        questions_asked = 0

        while questions_asked < budget:
            selection = select_next_topic(db, learner_id=learner.learner_id, subject_id=subject_id)
            record_topic_selection_event(
                db, learner_id=learner.learner_id, subject_id=subject_id, selection=selection
            )
            topic = topics_by_id[selection.topic_id]
            answer = draw_simulated_answer(
                topic, truly_mastered=true_mastery[topic.topic_id], rng=rng
            )
            result = apply_mastery_update(
                db,
                learner_id=learner.learner_id,
                subject_id=subject_id,
                topic_id=topic.topic_id,
                correct=answer.correct,
                question_type=answer.question_type,
            )
            db.commit()
            questions_asked += 1

            if result.posterior_band == MasteryBand.MASTERED:
                mastered_topic_ids.add(topic.topic_id)
            else:
                mastered_topic_ids.discard(topic.topic_id)

            if true_topic_ids <= mastered_topic_ids:
                return LearnerOutcome(questions_to_mastery=questions_asked, converged=True)

    return LearnerOutcome(questions_to_mastery=None, converged=False)


def run_random_condition(
    topics: list[Topic],
    *,
    true_mastery: dict[str, bool],
    max_questions_per_topic: int,
    rng: random.Random,
) -> LearnerOutcome:
    """Runs the random-order baseline for one simulated learner entirely
    in-memory (research.md §4, §6): each question, pick a topic uniformly
    at random from the subject's full topic set, independent of any
    mastery state. Convergence is scoped to topics this learner can
    genuinely master (`_true_topic_ids`) -- FR-004; Clarifications,
    session 2026-08-17. No DB writes -- this condition never calls
    `select_next_topic` and has no other reason to touch the database."""
    true_topic_ids = _true_topic_ids(true_mastery)
    if not true_topic_ids:
        return LearnerOutcome(questions_to_mastery=0, converged=True)

    budget = max_questions_per_topic * len(topics)
    observations: dict[str, MasteryObservation | None] = {topic.topic_id: None for topic in topics}

    questions_asked = 0
    while questions_asked < budget:
        topic = rng.choice(topics)
        answer = draw_simulated_answer(topic, truly_mastered=true_mastery[topic.topic_id], rng=rng)
        observations[topic.topic_id] = apply_bkt_update(
            observations[topic.topic_id],
            correct=answer.correct,
            question_type=answer.question_type,
        )
        questions_asked += 1

        if all(has_reached_mastered_band(observations[tid]) for tid in true_topic_ids):
            return LearnerOutcome(questions_to_mastery=questions_asked, converged=True)

    return LearnerOutcome(questions_to_mastery=None, converged=False)


def run_fixed_order_condition(
    topics: list[Topic],
    *,
    true_mastery: dict[str, bool],
    max_questions_per_topic: int,
    rng: random.Random,
) -> LearnerOutcome:
    """Runs the fixed canonical-order baseline for one simulated learner
    entirely in-memory (research.md §4, §6): topics are visited in
    ascending `order_index`, asking up to `max_questions_per_topic`
    questions about the current topic (fewer if it reaches the mastered
    band first) before advancing. After one full pass, any topics still
    unmastered are re-cycled in the same order, repeating until every
    topic this learner can genuinely master (`_true_topic_ids`) is
    mastered, or the overall budget (`max_questions_per_topic *
    len(topics)`) is exhausted (FR-004; Clarifications, session
    2026-08-17). No DB writes."""
    true_topic_ids = _true_topic_ids(true_mastery)
    if not true_topic_ids:
        return LearnerOutcome(questions_to_mastery=0, converged=True)

    ordered_topics = sorted(topics, key=lambda topic: topic.order_index)
    budget = max_questions_per_topic * len(topics)
    observations: dict[str, MasteryObservation | None] = {
        topic.topic_id: None for topic in ordered_topics
    }

    questions_asked = 0
    while questions_asked < budget:
        progressed = False
        for topic in ordered_topics:
            if has_reached_mastered_band(observations[topic.topic_id]):
                continue
            for _ in range(max_questions_per_topic):
                if questions_asked >= budget:
                    break
                answer = draw_simulated_answer(
                    topic, truly_mastered=true_mastery[topic.topic_id], rng=rng
                )
                observations[topic.topic_id] = apply_bkt_update(
                    observations[topic.topic_id],
                    correct=answer.correct,
                    question_type=answer.question_type,
                )
                questions_asked += 1
                progressed = True
                if all(has_reached_mastered_band(observations[tid]) for tid in true_topic_ids):
                    return LearnerOutcome(questions_to_mastery=questions_asked, converged=True)
                if has_reached_mastered_band(observations[topic.topic_id]):
                    break
            if questions_asked >= budget:
                break
        if not progressed:
            break

    return LearnerOutcome(questions_to_mastery=None, converged=False)
