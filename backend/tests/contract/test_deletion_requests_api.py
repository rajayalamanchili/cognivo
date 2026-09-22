"""Contract tests: `POST`/`GET /api/deletion-requests` match spec 020
contracts/api.md (FR-001, FR-006, FR-007, FR-009).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

import pytest

from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_guardian(client) -> str:
    response = client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 201, response.text
    return response.json()["guardian_id"]


def _register_instructor(client) -> str:
    response = client.post(
        "/api/auth/instructor/register",
        json={
            "email": f"instructor-{uuid.uuid4()}@example.com",
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _add_learner(client, display_name: str = "Test Learner") -> str:
    response = client.post("/api/learners", json={"display_name": display_name})
    assert response.status_code == 201, response.text
    return response.json()["learner_id"]


def test_guardian_may_submit_deletion_request_for_own_learner(client):
    _register_guardian(client)
    learner_id = _add_learner(client)

    response = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": learner_id}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["target_type"] == "learner"
    assert body["target_id"] == learner_id
    assert body["status"] == "pending"
    assert "deletion_request_id" in body
    assert "requested_at" in body


def test_instructor_may_submit_deletion_request_for_self(client):
    instructor_id = _register_instructor(client)

    response = client.post(
        "/api/deletion-requests", json={"target_type": "instructor", "target_id": instructor_id}
    )

    assert response.status_code == 201, response.text
    assert response.json()["target_type"] == "instructor"


def test_guardian_may_not_target_unrelated_learner(client, db_session):
    _register_guardian(client)

    # Seed an unrelated learner directly (a different guardian's).
    other_guardian = RealGuardianAccount(
        email=f"other-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(other_guardian)
    db_session.commit()
    db_session.refresh(other_guardian)
    other_learner = LearnerProfile(
        display_name="Unrelated", is_demo=False, guardian_id=other_guardian.guardian_id
    )
    db_session.add(other_learner)
    db_session.commit()
    db_session.refresh(other_learner)

    response = client.post(
        "/api/deletion-requests",
        json={"target_type": "learner", "target_id": str(other_learner.learner_id)},
    )

    assert response.status_code == 403, response.text


def test_nonexistent_target_returns_404(client):
    _register_guardian(client)

    response = client.post(
        "/api/deletion-requests",
        json={"target_type": "learner", "target_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404, response.text


def test_duplicate_pending_request_returns_409_with_id(client):
    _register_guardian(client)
    learner_id = _add_learner(client)

    first = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": learner_id}
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": learner_id}
    )

    assert second.status_code == 409, second.text
    body = second.json()
    assert body["error"] == "deletion_already_pending"
    assert body["deletion_request_id"] == first.json()["deletion_request_id"]


def test_demo_account_target_returns_403(client, db_session):
    # Self-targeting is otherwise unambiguously authorized, isolating the
    # is_demo guard as the only thing that could produce a 403 here.
    instructor_id = _register_instructor(client)
    db_session.query(RealInstructorAccount).filter(
        RealInstructorAccount.instructor_id == uuid.UUID(instructor_id)
    ).update({RealInstructorAccount.is_demo: True})
    db_session.commit()

    response = client.post(
        "/api/deletion-requests", json={"target_type": "instructor", "target_id": instructor_id}
    )

    assert response.status_code == 403, response.text


def test_status_check_pending_before_processing(client):
    _register_guardian(client)
    learner_id = _add_learner(client)

    submit = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": learner_id}
    )
    deletion_request_id = submit.json()["deletion_request_id"]

    response = client.get(f"/api/deletion-requests/{deletion_request_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["completed_at"] is None


def test_status_check_forbidden_for_non_requester(client):
    _register_guardian(client)
    learner_id = _add_learner(client)
    submit = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": learner_id}
    )
    deletion_request_id = submit.json()["deletion_request_id"]

    # A second, unrelated guardian session should not be able to check status.
    client.cookies.clear()
    _register_guardian(client)

    response = client.get(f"/api/deletion-requests/{deletion_request_id}")

    assert response.status_code == 403, response.text
