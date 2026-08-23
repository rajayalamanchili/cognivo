"""Integration test: `GET /api/auth/whoami` (contracts/api.md) --
the read-only session-identity check the frontend nav uses to decide
which menu to render. No session -> `null`; a guardian or instructor
session reports its own `account_type`; logging out clears it again.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_whoami_null_with_no_session(client):
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {"account_type": None}


def test_whoami_reports_guardian_session(client):
    client.post(
        "/api/auth/guardian/register",
        json={"email": "whoami-guardian@example.com", "password": "correct horse battery staple"},
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {"account_type": "guardian"}


def test_whoami_reports_instructor_session(client):
    client.post(
        "/api/auth/instructor/register",
        json={
            "email": "whoami-instructor@example.com",
            "password": "correct horse battery staple",
        },
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {"account_type": "instructor"}


def test_whoami_null_after_logout(client):
    client.post(
        "/api/auth/guardian/register",
        json={
            "email": "whoami-guardian-logout@example.com",
            "password": "correct horse battery staple",
        },
    )
    client.post("/api/auth/logout")
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {"account_type": None}
