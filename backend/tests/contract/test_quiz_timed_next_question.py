"""Contract tests: `GET /api/quizzes/{id}/next-question` expiry
handling (spec 022 FR-003, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_before_expiry_generates_a_question_normally(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
        assert start.status_code == 200, start.text
        next_q = client.get(f"/api/quizzes/{start.json()['quiz_session_id']}/next-question")
    assert next_q.status_code == 200, next_q.text
    assert next_q.json()["status"] == "in_progress"
    assert next_q.json()["question"] is not None


def test_past_expiry_returns_409_and_transitions_to_ended_early(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]

    quiz = db_session.get(QuizSession, quiz_session_id)
    quiz.started_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    db_session.commit()

    next_q = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert next_q.status_code == 409, next_q.text

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.ENDED_EARLY

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
