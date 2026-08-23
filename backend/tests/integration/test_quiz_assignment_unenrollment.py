"""Integration test: a learner unenrolled from the roster after being
targeted is blocked from starting (contracts/api.md, FR-011, T020;
quickstart.md scenario 6).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from tests.integration.quiz_assignment_helpers import (
    ENTRY_TOPIC,
    create_assignment,
    create_roster,
    join_roster,
    login_instructor,
    register_guardian_with_learner,
    register_instructor,
)

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _login_guardian(client, email):
    response = client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def test_unenrolled_target_blocked_from_starting(client, algebra_subject):
    register_instructor(client, "assign-unenroll-instructor@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="assign-unenroll-guardian@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    login_instructor(client, "assign-unenroll-instructor@example.com")
    assignment = create_assignment(
        client, roster_id=roster_id, topic_ids=[ENTRY_TOPIC], learner_ids=[learner_id]
    )

    unenroll = client.delete(f"/api/rosters/{roster_id}/enrollments/{learner_id}")
    assert unenroll.status_code == 204, unenroll.text

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-unenroll-guardian@example.com")
    response = client.post(
        f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_enrolled"}
