"""Contract tests: `POST /api/practice-sessions/{id}/end` (spec 022
FR-010, contracts/api.md). No "untimed" 404 case -- every
`PracticeSession` row is timed by construction.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

from fastapi.testclient import TestClient

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


def test_in_progress_session_ends_200(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": str(demo_learner.learner_id),
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text

    end = client.post(f"/api/practice-sessions/{start.json()['practice_session_id']}/end")
    assert end.status_code == 200, end.text
    assert end.json()["status"] == "ended_early"


def test_already_terminal_session_returns_409(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    _complete_placement(client, algebra_subject.subject_id)

    with patch_generation():
        start = client.post(
            "/api/practice-sessions",
            json={
                "learner_id": str(demo_learner.learner_id),
                "subject_id": algebra_subject.subject_id,
                "time_limit_seconds": 1800,
            },
        )
    assert start.status_code == 200, start.text
    practice_session_id = start.json()["practice_session_id"]

    first = client.post(f"/api/practice-sessions/{practice_session_id}/end")
    assert first.status_code == 200, first.text

    second = client.post(f"/api/practice-sessions/{practice_session_id}/end")
    assert second.status_code == 409, second.text
