"""Integration test: `GET /api/auth/whoami` (contracts/api.md) --
the read-only session-identity check the frontend nav uses to decide
which menu to render, and `identifier` for the "signed in as ..."
readout. No session -> `null`/`null`; a guardian or instructor session
reports its own `account_type` and login email; a demo instructor
session reports its seeded display name; logging out clears it again.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from scripts.seed_demo_instructor import seed_demo_instructor

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
    assert response.json() == {"account_type": None, "identifier": None}


def test_whoami_reports_guardian_session_with_email(client):
    client.post(
        "/api/auth/guardian/register",
        json={"email": "whoami-guardian@example.com", "password": "correct horse battery staple"},
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "account_type": "guardian",
        "identifier": "whoami-guardian@example.com",
    }


def test_whoami_reports_instructor_session_with_email(client):
    client.post(
        "/api/auth/instructor/register",
        json={
            "email": "whoami-instructor@example.com",
            "password": "correct horse battery staple",
        },
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "account_type": "instructor",
        "identifier": "whoami-instructor@example.com",
    }


def test_whoami_reports_demo_instructor_session_with_display_name(client):
    seeded = seed_demo_instructor()
    client.get("/api/demo-instructor")

    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "account_type": "demo_instructor",
        "identifier": seeded.display_name,
    }


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
    assert response.json() == {"account_type": None, "identifier": None}
