"""Contract tests: `POST /api/quizzes` timed request/response (spec 022
FR-001, FR-006, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_omitted_time_limit_is_unchanged_untimed_response(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5}
        )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["expires_at"] is None

    quiz = db_session.get(QuizSession, body["quiz_session_id"])
    assert quiz.time_limit_seconds is None


def test_valid_preset_time_limit_sets_expires_at(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["expires_at"] is not None

    quiz = db_session.get(QuizSession, body["quiz_session_id"])
    assert quiz.time_limit_seconds == 1800


def test_time_limit_outside_preset_list_is_rejected(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    start = client.post(
        "/api/quizzes",
        json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5, "time_limit_seconds": 123},
    )
    assert start.status_code == 422, start.text


def test_request_schema_has_no_client_elapsed_time_field(db_session, demo_learner, algebra_subject):
    """FR-006: nothing in the request lets a client assert its own
    elapsed/expiry time for the server to trust -- `time_limit_seconds`
    is a duration the server starts its own clock against
    (`started_at`), never a client-reported "how much time is left"."""
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={
                "topic_ids": [_ENTRY_TOPIC],
                "question_count": 5,
                "time_limit_seconds": 1800,
                "expires_at": "2099-01-01T00:00:00Z",
                "elapsed_seconds": 0,
            },
        )
    assert start.status_code == 200, start.text
    # Extra, unrecognized fields are ignored -- expires_at is still
    # server-derived from started_at + time_limit_seconds, not echoed
    # back from the request body.
    body = start.json()
    assert body["expires_at"] != "2099-01-01T00:00:00Z"
