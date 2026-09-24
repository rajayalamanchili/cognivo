"""Unit test: `backend/src/services/quiz/session.py`'s
`record_quiz_answer` completion path races a concurrent
`end_session_manually`/`check_and_expire_if_needed` transition (spec
022, PR #83 review finding) -- the third way a timed quiz's status can
reach a terminal state, which didn't share the other two's row-lock
guard against a concurrent transition.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from src.models.assessment_event import AssessmentEvent
from src.models.enums import (
    AssessmentEventType,
    DifficultyBand,
    QuestionType,
    QuizSessionStatus,
    ValidationStatus,
)
from src.models.generated_question import GeneratedQuestion
from src.models.quiz_session import QuizSession
from src.services.audit_log.writer import record_event
from src.services.quiz.session import end_session_manually, record_quiz_answer


def test_completion_after_concurrent_manual_end_does_not_clobber_it(
    db_session, demo_learner, algebra_subject
):
    """Mirrors the request interleaving from the review finding: request
    A already passed its own expiry/status check earlier and is now
    grading the quiz's final answer (record_quiz_answer's completion
    branch below); request B (a manual "end now") races ahead and
    commits `ended_early` first. Request A reaching the completion
    branch afterward must not overwrite that with `completed`."""
    topic = algebra_subject.topics[0]
    quiz = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
        time_limit_seconds=1800,
    )
    db_session.add(quiz)
    db_session.flush()

    question = GeneratedQuestion(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.NUMERIC,
        stem="2 + 2",
        answer_key={"correct_value": 4},
        validation_status=ValidationStatus.VALID,
        shown_at=datetime.datetime.now(datetime.UTC),
        quiz_session_id=quiz.quiz_session_id,
    )
    db_session.add(question)
    db_session.flush()

    # The ANSWER_SUBMITTED event record_quiz_answer expects to already
    # be flushed for this same question (its own docstring).
    record_event(
        db_session,
        learner_id=demo_learner.learner_id,
        event_type=AssessmentEventType.ANSWER_SUBMITTED,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        question_id=question.question_id,
        payload={"response": 4, "correct": True},
    )
    db_session.flush()

    # Request B: a concurrent manual "end now" that races ahead and
    # commits first.
    end_session_manually(db_session, session=quiz, session_type="quiz")
    db_session.commit()
    assert quiz.status == QuizSessionStatus.ENDED_EARLY

    # Request A: reaches the completion branch afterward, unaware the
    # session has already ended.
    record_quiz_answer(db_session, question=question, correct=True)
    db_session.commit()

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.ENDED_EARLY

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
            AssessmentEvent.payload["session_id"].as_string() == str(quiz.quiz_session_id),
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].payload["end_reason"] == "manually_ended_early"


def test_completion_still_completes_when_nothing_raced_it(
    db_session, demo_learner, algebra_subject
):
    """Control case: with no concurrent transition, the lock+re-check
    added for the race above must not block the ordinary completion
    path."""
    topic = algebra_subject.topics[0]
    quiz = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
        time_limit_seconds=1800,
    )
    db_session.add(quiz)
    db_session.flush()

    question = GeneratedQuestion(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.NUMERIC,
        stem="2 + 2",
        answer_key={"correct_value": 4},
        validation_status=ValidationStatus.VALID,
        shown_at=datetime.datetime.now(datetime.UTC),
        quiz_session_id=quiz.quiz_session_id,
    )
    db_session.add(question)
    db_session.flush()

    record_event(
        db_session,
        learner_id=demo_learner.learner_id,
        event_type=AssessmentEventType.ANSWER_SUBMITTED,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        question_id=question.question_id,
        payload={"response": 4, "correct": True},
    )
    db_session.flush()

    record_quiz_answer(db_session, question=question, correct=True)
    db_session.commit()

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.COMPLETED
    assert quiz.completed_at is not None

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
            AssessmentEvent.payload["session_id"].as_string() == str(quiz.quiz_session_id),
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].payload["end_reason"] == "completed"
