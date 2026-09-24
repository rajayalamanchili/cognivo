"""Contract test: `GET /api/quizzes/{id}` timed summary fields (spec
022 SC-005, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from fastapi.testclient import TestClient

from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_untimed_quiz_summary_has_null_timing_fields(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 5}
        )
    assert start.status_code == 200, start.text

    summary = client.get(f"/api/quizzes/{start.json()['quiz_session_id']}")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["time_limit_seconds"] is None
    assert body["elapsed_seconds"] is None
    assert body["end_reason"] is None


def test_timed_quiz_summary_has_timing_fields_after_manual_end(
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

    end = client.post(f"/api/quizzes/{quiz_session_id}/end")
    assert end.status_code == 200, end.text

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["time_limit_seconds"] == 1800
    assert isinstance(body["elapsed_seconds"], int)
    assert body["end_reason"] == "manually_ended_early"


def test_timed_quiz_summary_after_dedup_exhaustion(db_session, demo_learner, algebra_subject):
    """PR feedback: dedup-retry exhaustion (research.md §4's third
    `ended_early` trigger, alongside timer expiry and manual end) used to
    bypass `_end_timed_session` for a timed quiz, leaving
    elapsed_seconds/end_reason silently `None` in the summary."""
    from src.api.main import app

    client = TestClient(app)
    with patch_generation(stems=["identical stem"]):
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": 10, "time_limit_seconds": 1800},
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]

    with patch_generation(stems=["identical stem"]):
        next_q = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert next_q.status_code == 200, next_q.text
    assert next_q.json()["status"] == "ended_early"

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["time_limit_seconds"] == 1800
    assert isinstance(body["elapsed_seconds"], int)
    assert body["end_reason"] == "dedup_exhausted"


def test_timed_quiz_summary_after_timer_expiry(db_session, demo_learner, algebra_subject):
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

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["end_reason"] == "timer_expired"
