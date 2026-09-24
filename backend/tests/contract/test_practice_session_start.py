"""Contract tests: `POST /api/practice-sessions` (spec 022 FR-001,
FR-006, FR-008, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

from src.models.practice_session import PracticeSession
from tests.integration.quiz_helpers import patch_generation


def _complete_placement(client: TestClient, subject_id: str) -> str:
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
    return start.json()["placement_session_id"]


def test_valid_start_returns_session_and_first_question(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["expires_at"] is not None
    assert body["question"] is not None

    session = db_session.get(PracticeSession, body["practice_session_id"])
    assert session.time_limit_seconds == 1800
    assert session.subject_id == algebra_subject.subject_id


def test_unknown_subject_returns_404(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    start = client.post(
        "/api/practice-sessions",
        json={
            "subject_id": "not-a-real-subject",
            "time_limit_seconds": 1800,
        },
    )
    assert start.status_code == 404, start.text


def test_missing_time_limit_returns_422(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    start = client.post(
        "/api/practice-sessions",
        json={"subject_id": algebra_subject.subject_id},
    )
    assert start.status_code == 422, start.text


def test_invalid_time_limit_returns_422(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    start = client.post(
        "/api/practice-sessions",
        json={
            "subject_id": algebra_subject.subject_id,
            "time_limit_seconds": 42,
        },
    )
    assert start.status_code == 422, start.text


def test_request_schema_has_no_client_elapsed_time_field(
    db_session, demo_learner, algebra_subject
):
    """FR-006: extra fields (e.g. a client-asserted expires_at) are
    ignored -- the server derives expires_at from its own started_at."""
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )
    assert start.status_code == 200, start.text
    assert start.json()["expires_at"] != "2099-01-01T00:00:00Z"


def test_client_supplied_learner_id_is_ignored(db_session, demo_learner, algebra_subject):
    """A client-asserted learner_id must never let the caller start a
    session as someone else -- the server always resolves the demo
    learner itself, matching quiz.py's start_quiz_route pattern."""
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": "00000000-0000-0000-0000-000000000000",
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text

    session = db_session.get(PracticeSession, start.json()["practice_session_id"])
    assert session.learner_id == demo_learner.learner_id
