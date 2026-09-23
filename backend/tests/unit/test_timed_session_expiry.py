"""Unit tests: `backend/src/services/quiz/session.py`'s
`check_and_expire_if_needed` (spec 022 FR-003/FR-006/FR-007,
research.md §1). SC-002.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.quiz_session import QuizSession
from src.services.quiz.session import check_and_expire_if_needed


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def test_untimed_session_is_a_noop(db_session, demo_learner, algebra_subject):
    topic = algebra_subject.topics[0]
    quiz = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=5,
        status=QuizSessionStatus.IN_PROGRESS,
        time_limit_seconds=None,
    )
    db_session.add(quiz)
    db_session.commit()

    expired = check_and_expire_if_needed(db_session, session=quiz, session_type="quiz")

    assert expired is False
    assert quiz.status == QuizSessionStatus.IN_PROGRESS
    assert quiz.completed_at is None


def test_timed_session_before_expiry_is_untouched(db_session, demo_learner, algebra_subject):
    topic = algebra_subject.topics[0]
    quiz = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=5,
        status=QuizSessionStatus.IN_PROGRESS,
        time_limit_seconds=3600,
    )
    db_session.add(quiz)
    db_session.commit()

    expired = check_and_expire_if_needed(db_session, session=quiz, session_type="quiz")

    assert expired is False
    assert quiz.status == QuizSessionStatus.IN_PROGRESS


def test_timed_session_past_expiry_transitions_and_writes_one_event(
    db_session, demo_learner, algebra_subject
):
    topic = algebra_subject.topics[0]
    quiz = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=5,
        status=QuizSessionStatus.IN_PROGRESS,
        time_limit_seconds=1800,
    )
    db_session.add(quiz)
    db_session.commit()
    # Simulate a session started well past its 30-minute limit.
    quiz.started_at = _now() - datetime.timedelta(hours=1)
    db_session.commit()

    expired = check_and_expire_if_needed(db_session, session=quiz, session_type="quiz")
    db_session.commit()

    assert expired is True
    assert quiz.status == QuizSessionStatus.ENDED_EARLY
    assert quiz.completed_at is not None

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].payload["end_reason"] == "timer_expired"
    assert events[0].payload["session_type"] == "quiz"
    assert events[0].payload["session_id"] == str(quiz.quiz_session_id)
    assert events[0].payload["time_limit_seconds"] == 1800

    # Idempotent: calling again after it's already ended_early writes no
    # second event and doesn't raise.
    expired_again = check_and_expire_if_needed(db_session, session=quiz, session_type="quiz")
    db_session.commit()
    assert expired_again is False
    events_after = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
        )
        .all()
    )
    assert len(events_after) == 1
