"""Integration test: `GET /api/rosters/{roster_id}/assignments/
{assignment_id}` -- the per-student report (contracts/api.md, FR-009,
FR-010, T029; quickstart.md scenario 8).

Confirms a single response shows the correct status and score for a
mix of not_started/in_progress/completed/ended_early learners
simultaneously, not collapsed into a class-wide aggregate (SC-003).
`ended_early` is only exercised here (not in quickstart.md's manual
scenario 8) -- triggering it requires exhausting the dedup-retry
mechanism (`test_quiz_ended_early.py`'s existing pattern), not
something a manual walkthrough drives by hand.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from tests.integration.quiz_assignment_helpers import (
    ENTRY_TOPIC,
    create_assignment,
    create_roster,
    join_roster,
    register_guardian_with_learner,
    register_instructor,
)
from tests.integration.quiz_helpers import patch_generation

pytestmark = pytest.mark.usefixtures("database_available")

_INSTRUCTOR_EMAIL = "assign-report-instructor@example.com"


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _login_instructor(client):
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": _INSTRUCTOR_EMAIL, "password": "correct horse"},
    )
    assert response.status_code == 200, response.text


def _login_guardian(client, email):
    response = client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def test_report_shows_mixed_status_and_score_per_learner(client, algebra_subject):
    register_instructor(client, _INSTRUCTOR_EMAIL)
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    learners = {}
    for label in ("a", "b", "c", "d"):
        client.post("/api/auth/logout")
        _guardian_id, learner_id = register_guardian_with_learner(
            client,
            guardian_email=f"assign-report-guardian-{label}@example.com",
            learner_name=f"Learner {label.upper()}",
        )
        join_roster(client, learner_id=learner_id, join_code=join_code)
        learners[label] = learner_id

    client.post("/api/auth/logout")
    _login_instructor(client)
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        question_count=1,
        learner_ids=list(learners.values()),
    )
    assignment_id = assignment["assignment_id"]

    # Learner A: completes their one-question quiz.
    client.post("/api/auth/logout")
    _login_guardian(client, "assign-report-guardian-a@example.com")
    with patch_generation():
        start_a = client.post(f"/api/assignments/{assignment_id}/learners/{learners['a']}/start")
    assert start_a.status_code == 201, start_a.text
    answer_a = client.post(
        f"/api/questions/{start_a.json()['question']['question_id']}/answer",
        json={"response": 0},
    )
    assert answer_a.status_code == 200, answer_a.text

    # Learner B: starts but never answers -- stays in_progress.
    client.post("/api/auth/logout")
    _login_guardian(client, "assign-report-guardian-b@example.com")
    with patch_generation():
        start_b = client.post(f"/api/assignments/{assignment_id}/learners/{learners['b']}/start")
    assert start_b.status_code == 201, start_b.text

    # Learner C: never starts.

    # Learner D: exhausts dedup retries on the very first question ->
    # ended_early, mirroring test_quiz_ended_early.py's exact pattern
    # (a fresh assignment targeting only this learner, question_count
    # high enough that ended_early isn't just "reached question_count").
    client.post("/api/auth/logout")
    _login_instructor(client)
    solo_assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        question_count=10,
        learner_ids=[learners["d"]],
    )

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-report-guardian-d@example.com")
    with patch_generation(stems=["identical stem"]):
        start_d = client.post(
            f"/api/assignments/{solo_assignment['assignment_id']}/learners/{learners['d']}/start"
        )
    assert start_d.status_code == 201, start_d.text
    quiz_session_id_d = start_d.json()["quiz_session_id"]
    with patch_generation(stems=["identical stem"]):
        next_d = client.get(f"/api/quizzes/{quiz_session_id_d}/next-question")
    assert next_d.status_code == 200, next_d.text
    assert next_d.json()["status"] == "ended_early"

    client.post("/api/auth/logout")
    _login_instructor(client)
    report = client.get(f"/api/rosters/{roster_id}/assignments/{assignment_id}")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["assignment_id"] == assignment_id

    by_learner = {entry["learner_id"]: entry for entry in body["learners"]}
    assert by_learner[learners["a"]]["status"] == "completed"
    assert by_learner[learners["a"]]["score"] == {"correct": 1, "total": 1}
    assert by_learner[learners["a"]]["display_name"] == "Learner A"

    assert by_learner[learners["b"]]["status"] == "in_progress"
    assert by_learner[learners["b"]]["score"] is None

    assert by_learner[learners["c"]]["status"] == "not_started"
    assert by_learner[learners["c"]]["score"] is None

    solo_report = client.get(
        f"/api/rosters/{roster_id}/assignments/{solo_assignment['assignment_id']}"
    )
    assert solo_report.status_code == 200, solo_report.text
    solo_by_learner = {entry["learner_id"]: entry for entry in solo_report.json()["learners"]}
    assert solo_by_learner[learners["d"]]["status"] == "ended_early"
    assert solo_by_learner[learners["d"]]["score"] == {"correct": 0, "total": 0}


def test_report_403_for_non_owner(client, algebra_subject):
    register_instructor(client, _INSTRUCTOR_EMAIL)
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="assign-report-guardian-e@example.com", learner_name="Learner E"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    _login_instructor(client)
    assignment = create_assignment(
        client, roster_id=roster_id, topic_ids=[ENTRY_TOPIC], learner_ids=[learner_id]
    )

    client.post("/api/auth/logout")
    register_instructor(client, "assign-report-intruder@example.com")
    response = client.get(f"/api/rosters/{roster_id}/assignments/{assignment['assignment_id']}")
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_roster_owner"}
