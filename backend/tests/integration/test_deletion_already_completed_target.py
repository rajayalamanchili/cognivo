"""Integration test: a deletion request against an already-gone target
never errors or retries forever -- spec 020 Acceptance Scenario 4,
spec.md Edge Cases, SC-003.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

import pytest

from src.models.deletion_request import DeletionRequest
from src.models.learner_profile import LearnerProfile

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    return TestClient(app, base_url="https://testserver")


def test_submit_against_nonexistent_target_returns_404_not_a_partial_attempt(client):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert register.status_code == 201, register.text

    response = client.post(
        "/api/deletion-requests",
        json={"target_type": "learner", "target_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404, response.text


def test_target_deleted_before_cron_reaches_it_completes_without_error(client, db_session):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert register.status_code == 201, register.text

    learner_response = client.post("/api/learners", json={"display_name": "Soon Gone"})
    assert learner_response.status_code == 201, learner_response.text
    learner_id = uuid.UUID(learner_response.json()["learner_id"])

    submit = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": str(learner_id)}
    )
    assert submit.status_code == 201, submit.text
    deletion_request_id = uuid.UUID(submit.json()["deletion_request_id"])

    # A concurrent path (not this feature) deletes the learner directly,
    # before the cron executor ever reaches this request.
    db_session.query(LearnerProfile).filter(LearnerProfile.learner_id == learner_id).delete(
        synchronize_session=False
    )
    db_session.commit()

    execute = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text
    assert execute.json()["processed_count"] >= 1

    db_session.expunge_all()
    reloaded_request = db_session.get(DeletionRequest, deletion_request_id)
    assert reloaded_request.completed_at is not None
