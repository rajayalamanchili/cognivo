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
