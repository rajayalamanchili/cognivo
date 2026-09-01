"""Integration test: `GET /api/cron/classify-misconceptions` requires
`Authorization: Bearer $CRON_SECRET`, fails closed if unconfigured, and
on a valid request returns `200` with `{"status": "ok",
"classified_count": N}` (spec 013 contracts/api.md), T016 -- mirroring
`reset_demo_data_route`'s own auth pattern exactly
(`api/routes/cron.py`).
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
        "/api/cron/classify-misconceptions", headers={"Authorization": "Bearer anything"}
    )
    assert response.status_code == 503


def test_returns_401_on_secret_mismatch(client, db_session, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    response = client.get(
        "/api/cron/classify-misconceptions", headers={"Authorization": "Bearer wrong-secret"}
    )
    assert response.status_code == 401


def test_returns_401_with_no_authorization_header(client, db_session, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    response = client.get("/api/cron/classify-misconceptions")
    assert response.status_code == 401


def test_valid_request_returns_ok_with_classified_count(client, db_session, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    response = client.get(
        "/api/cron/classify-misconceptions",
        headers={"Authorization": "Bearer the-real-secret"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["classified_count"], int)
    assert body["classified_count"] == 0  # no learners/answers exist in this test's fresh DB
