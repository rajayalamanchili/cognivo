"""Integration test: a second join attempt for the same (learner,
roster) pair while a request is already pending returns the existing
pending request, not a duplicate (Edge Cases, T028).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.enrollment_request import EnrollmentRequest

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client, email="teacher@example.com"):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _register_guardian_with_learner(client, email="parent@example.com", display_name="Jamie"):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def test_duplicate_closed_join_returns_existing_pending_request(
    client, db_session, algebra_subject
):
    _register_instructor(client)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "closed"}
    )
    roster_id = roster.json()["roster_id"]
    join_code = roster.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)

    first = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert first.status_code == 202, first.text
    first_request_id = first.json()["enrollment_request_id"]

    second = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert second.status_code == 202, second.text
    assert second.json()["enrollment_request_id"] == first_request_id

    db_session.expire_all()
    pending_count = (
        db_session.query(EnrollmentRequest)
        .filter(
            EnrollmentRequest.learner_id == uuid.UUID(learner_id),
            EnrollmentRequest.roster_id == uuid.UUID(roster_id),
        )
        .count()
    )
    assert pending_count == 1


def test_duplicate_open_join_returns_existing_enrollment(client, algebra_subject):
    _register_instructor(client)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    join_code = roster.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)

    first = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert first.status_code == 201, first.text
    first_enrollment_id = first.json()["enrollment_id"]

    second = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert second.status_code == 201, second.text
    assert second.json()["enrollment_id"] == first_enrollment_id
