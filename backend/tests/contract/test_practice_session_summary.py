"""Contract test: `GET /api/practice-sessions/{id}` summary fields
(spec 022 SC-005, contracts/api.md) -- always non-null, unlike the
quiz summary's untimed-null case, since every PracticeSession row is
timed by construction.

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


def test_summary_has_score_and_timing_fields_after_manual_end(
    db_session, demo_learner, algebra_subject
):
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
    question_id = start.json()["question"]["question_id"]

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 1})
    assert answer.status_code == 200, answer.text

    end = client.post(f"/api/practice-sessions/{practice_session_id}/end")
    assert end.status_code == 200, end.text

    summary = client.get(f"/api/practice-sessions/{practice_session_id}")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["score"]["total"] == 1
    assert body["time_limit_seconds"] == 1800
    assert isinstance(body["elapsed_seconds"], int)
    assert body["end_reason"] == "manually_ended_early"
