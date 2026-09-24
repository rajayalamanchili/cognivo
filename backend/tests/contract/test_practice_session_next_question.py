"""Contract tests: `GET /api/practice-sessions/{id}/next-question`
expiry handling (spec 022 FR-003, contracts/api.md) -- mirrors
test_quiz_timed_next_question.py's quiz behavior for the practice route.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.practice_session import PracticeSession
from tests.integration.quiz_helpers import patch_generation


def _complete_placement(client: TestClient, subject_id: str) -> None:
    with patch_generation():
        start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text


def _start_practice_session(client: TestClient, learner_id, subject_id: str) -> dict:
    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": str(learner_id),
                "subject_id": subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text
    return start.json()


def test_before_expiry_generates_a_question_normally(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)
    start = _start_practice_session(client, demo_learner.learner_id, algebra_subject.subject_id)

    with patch_generation():
        next_q = client.get(
            f"/api/practice-sessions/{start['practice_session_id']}/next-question"
        )
    assert next_q.status_code == 200, next_q.text
    assert next_q.json()["status"] == "in_progress"
    assert next_q.json()["question"] is not None


def test_past_expiry_returns_409_and_transitions_to_ended_early(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)
    start = _start_practice_session(client, demo_learner.learner_id, algebra_subject.subject_id)
    practice_session_id = start["practice_session_id"]

    session = db_session.get(PracticeSession, practice_session_id)
    session.started_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
    db_session.commit()

    next_q = client.get(f"/api/practice-sessions/{practice_session_id}/next-question")
    assert next_q.status_code == 409, next_q.text

    db_session.refresh(session)
    assert session.status == QuizSessionStatus.ENDED_EARLY

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
    assert events[0].payload["session_type"] == "practice"
