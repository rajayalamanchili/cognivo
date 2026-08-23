"""Integration test: instructor A's dashboard never includes instructor
B's roster/learners; a direct request for B's roster from A's session
returns `403` (quickstart scenario 7, SC-002, T038).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _login_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def _register_guardian_with_learner(client, email, display_name):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def test_instructor_a_cannot_view_instructor_b_dashboard(client, algebra_subject, biology_subject):
    _register_instructor(client, "instructor-g@example.com")
    roster_a = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_a_id = roster_a.json()["roster_id"]
    join_code_a = roster_a.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_a_id = _register_guardian_with_learner(client, "parent-g@example.com", "Learner A")
    client.post("/api/rosters/join", json={"learner_id": learner_a_id, "join_code": join_code_a})

    client.post("/api/auth/logout")
    _register_instructor(client, "instructor-h@example.com")
    roster_b = client.post(
        "/api/rosters", json={"subject_id": biology_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_b_id = roster_b.json()["roster_id"]
    join_code_b = roster_b.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_b_id = _register_guardian_with_learner(client, "parent-h@example.com", "Learner B")
    client.post("/api/rosters/join", json={"learner_id": learner_b_id, "join_code": join_code_b})

    # Instructor B's own dashboard: only Learner B, never Learner A.
    client.post("/api/auth/logout")
    _login_instructor(client, "instructor-h@example.com")
    dashboard_b = client.get(f"/api/rosters/{roster_b_id}/dashboard")
    assert dashboard_b.status_code == 200, dashboard_b.text
    b_learner_ids = {entry["learner_id"] for entry in dashboard_b.json()["learners"]}
    assert b_learner_ids == {learner_b_id}
    assert learner_a_id not in b_learner_ids

    # Instructor B requesting instructor A's roster directly -> 403.
    forbidden = client.get(f"/api/rosters/{roster_a_id}/dashboard")
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "not_roster_owner"}


def test_dashboard_for_unknown_roster_returns_404(client):
    _register_instructor(client, "instructor-i@example.com")
    response = client.get("/api/rosters/00000000-0000-0000-0000-000000000000/dashboard")
    assert response.status_code == 404
