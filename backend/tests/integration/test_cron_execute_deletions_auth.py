"""Integration test: `GET /api/cron/execute-deletions` requires
`Authorization: Bearer $CRON_SECRET`, fails closed if unconfigured, and
on a valid request returns `200` with the sweep/execution counts (spec
020 contracts/api.md) -- mirrors `classify_misconceptions_route`'s own
auth pattern exactly (`api/routes/cron.py`).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


def test_returns_503_when_cron_secret_unconfigured(client, db_session, monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    response = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer anything"}
    )
    assert response.status_code == 503


def test_returns_401_on_secret_mismatch(client, db_session, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    response = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer wrong-secret"}
    )
    assert response.status_code == 401


def test_returns_401_with_no_authorization_header(client, db_session, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    response = client.get("/api/cron/execute-deletions")
    assert response.status_code == 401


def test_valid_request_returns_ok_with_counts(client, db_session, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    response = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["swept_count"], int)
    assert isinstance(body["processed_count"], int)
    assert isinstance(body["remaining_pending_count"], int)


def test_one_failing_request_does_not_block_the_rest_of_the_batch(client, db_session, monkeypatch):
    """PR #79 review: a deletion that reliably fails to execute must not
    permanently stall every request behind it in the queue."""
    import uuid

    from src.models.deletion_request import DeletionRequest
    from src.models.enums import DeletionTargetType
    from src.models.real_guardian_account import RealGuardianAccount

    monkeypatch.setenv("CRON_SECRET", "the-real-secret")

    poison_guardian = RealGuardianAccount(
        email=f"poison-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    healthy_guardian = RealGuardianAccount(
        email=f"healthy-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add_all([poison_guardian, healthy_guardian])
    db_session.commit()
    db_session.refresh(poison_guardian)
    db_session.refresh(healthy_guardian)

    poison_request = DeletionRequest(
        target_type=DeletionTargetType.GUARDIAN,
        target_id=poison_guardian.guardian_id,
        requested_by="test",
    )
    healthy_request = DeletionRequest(
        target_type=DeletionTargetType.GUARDIAN,
        target_id=healthy_guardian.guardian_id,
        requested_by="test",
    )
    db_session.add_all([poison_request, healthy_request])
    db_session.commit()
    db_session.refresh(poison_request)
    db_session.refresh(healthy_request)

    import src.api.routes.cron as cron_module

    original_execute_deletion = cron_module.execute_deletion

    def failing_for_poison(db, deletion_request):
        if deletion_request.target_id == poison_guardian.guardian_id:
            raise RuntimeError("simulated poison-message failure")
        return original_execute_deletion(db, deletion_request)

    monkeypatch.setattr(cron_module, "execute_deletion", failing_for_poison)

    response = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["processed_count"] >= 1

    db_session.expunge_all()
    reloaded_poison = db_session.get(DeletionRequest, poison_request.deletion_request_id)
    reloaded_healthy = db_session.get(DeletionRequest, healthy_request.deletion_request_id)
    assert reloaded_poison.completed_at is None
    assert reloaded_healthy.completed_at is not None
