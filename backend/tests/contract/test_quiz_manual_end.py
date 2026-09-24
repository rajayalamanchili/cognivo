"""Contract tests: `POST /api/quizzes/{id}/end` (spec 022 FR-010,
contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_timed_in_progress_quiz_ends_200(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]

    end = client.post(f"/api/quizzes/{quiz_session_id}/end")
    assert end.status_code == 200, end.text
    assert end.json()["status"] == "ended_early"


def test_untimed_quiz_returns_404(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5}
        )
    assert start.status_code == 200, start.text

    end = client.post(f"/api/quizzes/{start.json()['quiz_session_id']}/end")
    assert end.status_code == 404, end.text


def test_already_terminal_quiz_returns_409(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]

    first = client.post(f"/api/quizzes/{quiz_session_id}/end")
    assert first.status_code == 200, first.text

    second = client.post(f"/api/quizzes/{quiz_session_id}/end")
    assert second.status_code == 409, second.text


def test_manual_end_after_silent_deadline_records_timer_expired(
    db_session, demo_learner, algebra_subject
):
    """PR feedback: a manual "end now" arriving after the real deadline
    has already passed (but before anything else ran the lazy expiry
    check) must record `end_reason=timer_expired`, not
    `manually_ended_early` -- the route runs the expiry check first."""
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 900},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]

    quiz = db_session.get(QuizSession, quiz_session_id)
    quiz.started_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1000)
    db_session.commit()

    end = client.post(f"/api/quizzes/{quiz_session_id}/end")
    assert end.status_code == 409, end.text

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
        )
        .one()
    )
    assert event.payload["end_reason"] == "timer_expired"
