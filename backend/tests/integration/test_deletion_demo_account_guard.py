"""Integration test: a demo account is never reachable through the
real-account deletion pathway, checked at both submission time and,
as defense-in-depth, inside the cron executor itself (spec 020 FR-007,
research.md R7).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

import pytest

from src.models.deletion_request import DeletionRequest
from src.models.enums import DeletionTargetType
from src.models.learner_profile import LearnerProfile

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    return TestClient(app, base_url="https://testserver")


def test_submission_rejects_demo_target(client, db_session):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert register.status_code == 201, register.text
    guardian_id = uuid.UUID(register.json()["guardian_id"])

    demo_learner = LearnerProfile(
        display_name="Demo Learner", is_demo=True, guardian_id=guardian_id
    )
    db_session.add(demo_learner)
    db_session.commit()
    db_session.refresh(demo_learner)

    response = client.post(
        "/api/deletion-requests",
        json={"target_type": "learner", "target_id": str(demo_learner.learner_id)},
    )

    assert response.status_code == 403, response.text


def test_cron_executor_refuses_a_pending_request_whose_target_is_demo(client, db_session):
    """Simulates a request that reached `pending` despite targeting a
    demo account (e.g. `is_demo` flipped after submission) -- the cron
    executor must still refuse to process it, not just the submission
    endpoint."""
    demo_learner = LearnerProfile(display_name="Demo Learner", is_demo=True)
    db_session.add(demo_learner)
    db_session.commit()
    db_session.refresh(demo_learner)
    learner_id = demo_learner.learner_id

    deletion_request = DeletionRequest(
        target_type=DeletionTargetType.LEARNER, target_id=learner_id, requested_by="test"
    )
    db_session.add(deletion_request)
    db_session.commit()
    db_session.refresh(deletion_request)
    deletion_request_id = deletion_request.deletion_request_id

    execute = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text

    db_session.expunge_all()
    assert db_session.get(LearnerProfile, learner_id) is not None
    assert db_session.get(DeletionRequest, deletion_request_id).completed_at is None
