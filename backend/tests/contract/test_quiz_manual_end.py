"""Contract tests: `POST /api/quizzes/{id}/end` (spec 022 FR-010,
contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

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
