"""Integration test: `POST /api/tutor/sessions` -- create, get-or-create
per FR-014, and the guardian-mediated/demo-learner auth split (FR-001),
T016.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from tests.integration.quiz_assignment_helpers import register_guardian_with_learner

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_demo_learner_creates_then_reuses_session(client, demo_learner, biology_subject):
    first = client.post(
        "/api/tutor/sessions",
        json={"learner_id": str(demo_learner.learner_id), "subject_id": biology_subject.subject_id},
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["status"] == "active"
    assert body["subject_id"] == biology_subject.subject_id

    second = client.post(
        "/api/tutor/sessions",
        json={"learner_id": str(demo_learner.learner_id), "subject_id": biology_subject.subject_id},
    )
    assert second.status_code == 200, second.text
    assert second.json()["session_id"] == body["session_id"]


def test_guardians_own_learner_creates_session(client, biology_subject):
    guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="tutor-sessions-guardian@example.com", learner_name="Learner"
    )
    response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": learner_id, "subject_id": biology_subject.subject_id},
    )
    assert response.status_code == 201, response.text
    assert response.json()["subject_id"] == biology_subject.subject_id


def test_different_subject_gets_a_different_session(client, biology_subject, algebra_subject):
    guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="tutor-sessions-multi-subject@example.com", learner_name="Learner"
    )
    biology_session = client.post(
        "/api/tutor/sessions",
        json={"learner_id": learner_id, "subject_id": biology_subject.subject_id},
    )
    algebra_session = client.post(
        "/api/tutor/sessions",
        json={"learner_id": learner_id, "subject_id": algebra_subject.subject_id},
    )
    assert biology_session.status_code == 201, biology_session.text
    assert algebra_session.status_code == 201, algebra_session.text
    assert biology_session.json()["session_id"] != algebra_session.json()["session_id"]


def test_403_when_guardian_does_not_own_learner(client, biology_subject):
    _owner_guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="tutor-sessions-owner@example.com", learner_name="Owned Learner"
    )
    client.post("/api/auth/logout")
    register_guardian_with_learner(
        client, guardian_email="tutor-sessions-other@example.com", learner_name="Other Learner"
    )

    response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": learner_id, "subject_id": biology_subject.subject_id},
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}


def test_403_for_real_learner_with_no_session_at_all(client, biology_subject):
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="tutor-sessions-noauth@example.com", learner_name="Learner"
    )
    client.post("/api/auth/logout")

    response = client.post(
        "/api/tutor/sessions",
        json={"learner_id": learner_id, "subject_id": biology_subject.subject_id},
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}
