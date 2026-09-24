"""Unit tests: `backend/src/services/quiz/session.py`'s
`end_session_manually` (spec 022 FR-007/FR-010, research.md §4).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import pytest

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.quiz_session import QuizSession
from src.services.quiz.session import (
    SessionAlreadyEndedError,
    SessionNotTimedError,
    end_session_manually,
)


def _make_quiz(
    db_session, *, learner, subject, time_limit_seconds, status=QuizSessionStatus.IN_PROGRESS
):
    topic = subject.topics[0]
    quiz = QuizSession(
        learner_id=learner.learner_id,
        subject_id=subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=5,
        status=status,
        time_limit_seconds=time_limit_seconds,
    )
    db_session.add(quiz)
    db_session.commit()
    return quiz


def test_timed_in_progress_session_ends_correctly(db_session, demo_learner, algebra_subject):
    quiz = _make_quiz(
        db_session, learner=demo_learner, subject=algebra_subject, time_limit_seconds=1800
    )

    end_session_manually(db_session, session=quiz, session_type="quiz")
    db_session.commit()

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
    assert events[0].payload["end_reason"] == "manually_ended_early"


def test_untimed_session_is_rejected(db_session, demo_learner, algebra_subject):
    quiz = _make_quiz(
        db_session, learner=demo_learner, subject=algebra_subject, time_limit_seconds=None
    )

    with pytest.raises(SessionNotTimedError):
        end_session_manually(db_session, session=quiz, session_type="quiz")

    assert quiz.status == QuizSessionStatus.IN_PROGRESS


def test_already_terminal_session_is_rejected(db_session, demo_learner, algebra_subject):
    quiz = _make_quiz(
        db_session,
        learner=demo_learner,
        subject=algebra_subject,
        time_limit_seconds=1800,
        status=QuizSessionStatus.COMPLETED,
    )

    with pytest.raises(SessionAlreadyEndedError):
        end_session_manually(db_session, session=quiz, session_type="quiz")
