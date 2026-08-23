"""Integration test: instructor A's `GET /api/rosters` never includes
instructor B's rosters (SC-002's "roster list" path, `/speckit-analyze`
finding F2, T029a).

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


def test_roster_list_is_scoped_to_requesting_instructor(client, algebra_subject, biology_subject):
    _register_instructor(client, "instructor-a@example.com")
    roster_a = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    assert roster_a.status_code == 201, roster_a.text
    roster_a_id = roster_a.json()["roster_id"]

    client.post("/api/auth/logout")
    _register_instructor(client, "instructor-b@example.com")
    roster_b = client.post(
        "/api/rosters", json={"subject_id": biology_subject.subject_id, "enrollment_mode": "open"}
    )
    assert roster_b.status_code == 201, roster_b.text
    roster_b_id = roster_b.json()["roster_id"]

    list_b = client.get("/api/rosters")
    assert list_b.status_code == 200
    b_roster_ids = {roster["roster_id"] for roster in list_b.json()["rosters"]}
    assert b_roster_ids == {roster_b_id}
    assert roster_a_id not in b_roster_ids

    client.post("/api/auth/logout")
    _login_instructor(client, "instructor-a@example.com")
    list_a = client.get("/api/rosters")
    assert list_a.status_code == 200
    a_roster_ids = {roster["roster_id"] for roster in list_a.json()["rosters"]}
    assert a_roster_ids == {roster_a_id}
    assert roster_b_id not in a_roster_ids


def test_patch_roster_owned_by_another_instructor_returns_403(client, algebra_subject):
    _register_instructor(client, "instructor-c@example.com")
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_id = roster.json()["roster_id"]

    client.post("/api/auth/logout")
    _register_instructor(client, "instructor-d@example.com")
    response = client.patch(f"/api/rosters/{roster_id}", json={"enrollment_mode": "closed"})
    assert response.status_code == 403
    assert response.json() == {"detail": "not_roster_owner"}
