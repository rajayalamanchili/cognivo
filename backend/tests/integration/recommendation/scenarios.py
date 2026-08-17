"""Scripted mastery-state/assessment-event fixture builders for the
Recommendation Agent's test suite (spec 002 FR-009/SC-005).

MUST NOT be imported by, and MUST NOT import from, any Sequencing test
file (`tests/integration/test_next_topic_*.py`) -- this module and
those files sharing zero fixtures/helpers is exactly what
`scripts/check_no_shared_recommendation_sequencing_fixtures.py`
mechanically enforces (research.md §6).

Each helper below builds one topic's answered-question history against
a real Postgres-backed `algebra_subject` (see `tests/conftest.py`),
ending at a chosen `p_mastery`/`update_count` -- the same "hand-craft
MasteryState directly against real content" pattern
`tests/integration/test_next_topic_eligibility.py` already uses for
Sequencing, applied here to Recommendation's own scenarios.
"""

import uuid

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState

STRUGGLING_P = 0.2
DEVELOPING_P = 0.5
MASTERED_P = 0.85
MASTERED_CONSECUTIVE = 2


def _record_answer(
    db_session,
    *,
    learner_id,
    subject_id,
    topic_id,
    prior_p_mastery,
    posterior_p_mastery,
    correct,
):
    """One answered question: a `GeneratedQuestion` plus its
    `mastery_updated` `AssessmentEvent` -- the citation unit
    `weak_area.py`'s evidence assembly reads (FR-002)."""
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem=f"scenario question for {topic_id} ({uuid.uuid4().hex[:8]})",
        options=["a", "b", "c", "d"],
        answer_key={"correct_index": 0},
        validation_status=ValidationStatus.VALID,
    )
    db_session.add(question)
    db_session.flush()

    event = AssessmentEvent(
        learner_id=learner_id,
        event_type=AssessmentEventType.MASTERY_UPDATED,
        question_id=question.question_id,
        subject_id=subject_id,
        topic_id=topic_id,
        payload={
            "prior_p_mastery": prior_p_mastery,
            "posterior_p_mastery": posterior_p_mastery,
            "answer_correct": correct,
            "bkt_params_used": {"p_l0": 0.3, "p_t": 0.1, "p_s": 0.1, "p_g": 0.25},
        },
    )
    db_session.add(event)
    db_session.flush()
    return question, event


def set_topic_mastery(
    db_session,
    *,
    learner_id,
    subject_id,
    topic_id,
    final_p_mastery,
    num_events,
    consecutive_mastered_observations=0,
):
    """Builds `num_events` answered-question events for `topic_id`,
    all landing at `final_p_mastery`, and the resulting `MasteryState`
    row -- the general-purpose scripted-scenario primitive every
    helper below is built from. Every real trajectory converges to
    some final value; scenarios here only need that final value and
    the event *count*, not a specific intermediate path."""
    if num_events < 1:
        raise ValueError("num_events must be >= 1 to create any MasteryState row")

    for i in range(num_events):
        prior = None if i == 0 else final_p_mastery
        _record_answer(
            db_session,
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            prior_p_mastery=prior,
            posterior_p_mastery=final_p_mastery,
            correct=final_p_mastery >= 0.4,
        )

    state = db_session.get(MasteryState, (learner_id, subject_id, topic_id))
    if state is None:
        state = MasteryState(
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            p_mastery=final_p_mastery,
            update_count=num_events,
            consecutive_mastered_observations=consecutive_mastered_observations,
        )
        db_session.add(state)
    else:
        state.p_mastery = final_p_mastery
        state.update_count = num_events
        state.consecutive_mastered_observations = consecutive_mastered_observations
    db_session.commit()
    return state


def make_weak_topic(
    db_session, *, learner_id, subject_id, topic_id, num_events=3, p_mastery=STRUGGLING_P
):
    """A confidently-assessed, struggling-band topic (FR-002) -- the
    baseline "flagged weak area" scenario."""
    return set_topic_mastery(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        final_p_mastery=p_mastery,
        num_events=num_events,
    )


def make_in_progress_topic(
    db_session, *, learner_id, subject_id, topic_id, num_events=3, p_mastery=DEVELOPING_P
):
    """A confidently-assessed, developing-band topic (FR-003a) --
    "in progress," never flagged as weak."""
    return set_topic_mastery(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        final_p_mastery=p_mastery,
        num_events=num_events,
    )


def make_insufficient_data_topic(
    db_session, *, learner_id, subject_id, topic_id, num_events=1, p_mastery=STRUGGLING_P
):
    """A topic with 1-2 recorded events (< FR-004's 3-event minimum) --
    "insufficient data for this topic," never confidently flagged
    weak/in-progress/mastered regardless of `p_mastery`."""
    if not 1 <= num_events < 3:
        raise ValueError("insufficient-data scenario requires exactly 1 or 2 events")
    return set_topic_mastery(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        final_p_mastery=p_mastery,
        num_events=num_events,
    )


def make_mastered_topic(
    db_session, *, learner_id, subject_id, topic_id, num_events=3, p_mastery=MASTERED_P
):
    """A confidently-assessed, mastered-band topic (two consecutive
    >=0.7 observations, per Milestone 1's Mastered-confirmation rule)
    -- used as a satisfied-prerequisite fixture and to prove mastered
    topics are omitted from the report (spec.md Key Entities)."""
    return set_topic_mastery(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        final_p_mastery=p_mastery,
        num_events=num_events,
        consecutive_mastered_observations=MASTERED_CONSECUTIVE,
    )
