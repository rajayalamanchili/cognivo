"""Scripted free-text-answer fixture builders for the misconception
classifier's test suite (spec 013).

Distinct from `tests/integration/recommendation/scenarios.py`'s own
helpers (multiple_choice questions, `mastery_updated`-only history):
`classify.py`'s evidence is `answer_submitted` events on `free_text`
questions specifically, so these helpers record both the
`answer_submitted` and its paired `mastery_updated` event per answer --
the exact two-event shape `api/routes/questions.py`'s real free-text
answer path writes -- plus the resulting `MasteryState` row
`weak_area.py` needs to flag a topic as weak.
"""

import uuid

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState


def record_free_text_answer(
    db_session,
    *,
    learner_id,
    subject_id,
    topic_id,
    response,
    correct,
    prior_p_mastery,
    posterior_p_mastery,
):
    """One graded free-text answer: a `GeneratedQuestion`
    (`question_type=free_text`) plus its paired `answer_submitted` and
    `mastery_updated` events."""
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.FREE_TEXT,
        stem=f"scenario free-text question for {topic_id} ({uuid.uuid4().hex[:8]})",
        options=None,
        answer_key={"criteria": [{"description": "placeholder", "weight": 1.0}]},
        validation_status=ValidationStatus.VALID,
    )
    db_session.add(question)
    db_session.flush()

    answer_event = AssessmentEvent(
        learner_id=learner_id,
        event_type=AssessmentEventType.ANSWER_SUBMITTED,
        question_id=question.question_id,
        subject_id=subject_id,
        topic_id=topic_id,
        payload={
            "response": response,
            "correct": correct,
            "graduated_score": 1.0 if correct else 0.0,
            "threshold_used": 0.7,
            "criteria_met": [],
            "criteria_missed": [],
            "grading_logic_version": "v1",
        },
    )
    db_session.add(answer_event)

    mastery_event = AssessmentEvent(
        learner_id=learner_id,
        event_type=AssessmentEventType.MASTERY_UPDATED,
        question_id=question.question_id,
        subject_id=subject_id,
        topic_id=topic_id,
        payload={
            "prior_p_mastery": prior_p_mastery,
            "posterior_p_mastery": posterior_p_mastery,
            "answer_correct": correct,
            "bkt_params_used": {"p_l0": 0.3, "p_t": 0.1, "p_s": 0.1, "p_g": 0.05},
        },
    )
    db_session.add(mastery_event)
    db_session.flush()
    return question, answer_event, mastery_event


def record_qualifying_wrong_answers(
    db_session, *, learner_id, subject_id, topic_id, responses, final_p_mastery=0.2
):
    """Records one incorrect free-text answer per entry in `responses`
    and sets the resulting `MasteryState` row to `final_p_mastery` --
    mirrors `recommendation/scenarios.py`'s `set_topic_mastery`, so
    `weak_area.py` also flags the topic as weak when `len(responses)
    >= CONFIDENT_MIN_EVENTS` and `final_p_mastery` is struggling-band.
    """
    recorded = []
    for i, response in enumerate(responses):
        prior = None if i == 0 else final_p_mastery
        recorded.append(
            record_free_text_answer(
                db_session,
                learner_id=learner_id,
                subject_id=subject_id,
                topic_id=topic_id,
                response=response,
                correct=False,
                prior_p_mastery=prior,
                posterior_p_mastery=final_p_mastery,
            )
        )

    state = db_session.get(MasteryState, (learner_id, subject_id, topic_id))
    if state is None:
        state = MasteryState(
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            p_mastery=final_p_mastery,
            update_count=len(responses),
        )
        db_session.add(state)
    else:
        state.p_mastery = final_p_mastery
        state.update_count = len(responses)
    db_session.commit()
    return recorded
