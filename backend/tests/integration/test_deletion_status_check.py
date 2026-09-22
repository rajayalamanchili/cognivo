"""Integration test: `GET /api/deletion-requests/{id}` reflects reality
before and after the cron executor processes a request, and never
exposes any key beyond the status envelope itself -- in particular,
never any of the target's own data (spec 020 Acceptance Scenarios 1-2,
FR-009, SC-005).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

import pytest

_ALLOWED_KEYS = {"deletion_request_id", "target_type", "status", "requested_at", "completed_at"}


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    return TestClient(app, base_url="https://testserver")


def test_status_reflects_pending_then_completed_with_no_extra_keys(client):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert register.status_code == 201, register.text

    learner_response = client.post("/api/learners", json={"display_name": "Status Check"})
    assert learner_response.status_code == 201, learner_response.text
    learner_id = learner_response.json()["learner_id"]

    submit = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": learner_id}
    )
    assert submit.status_code == 201, submit.text
    deletion_request_id = submit.json()["deletion_request_id"]

    before = client.get(f"/api/deletion-requests/{deletion_request_id}")
    assert before.status_code == 200, before.text
    before_body = before.json()
    assert set(before_body.keys()) == _ALLOWED_KEYS
    assert before_body["status"] == "pending"
    assert before_body["completed_at"] is None

    execute = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text

    after = client.get(f"/api/deletion-requests/{deletion_request_id}")
    assert after.status_code == 200, after.text
    after_body = after.json()
    assert set(after_body.keys()) == _ALLOWED_KEYS
    assert after_body["status"] == "completed"
    assert after_body["completed_at"] is not None

    # No key here is ever the deleted learner's own data -- there simply
    # is no field for it, by construction of the allowlist above (not
    # even the target's own id).
    assert "display_name" not in after_body
    assert "target_id" not in after_body
