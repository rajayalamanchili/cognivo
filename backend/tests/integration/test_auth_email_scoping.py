"""Integration test: the same email registers successfully as both a
guardian and an instructor independently (quickstart scenario 2,
FR-002a, T018).

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


def test_same_email_registers_as_guardian_and_instructor(client):
    email = "parent-and-teacher@example.com"
    password = "correct horse battery staple"

    guardian_register = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": password}
    )
    assert guardian_register.status_code == 201, guardian_register.text

    instructor_register = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": password}
    )
    assert instructor_register.status_code == 201, instructor_register.text

    assert guardian_register.json()["guardian_id"] != instructor_register.json()["instructor_id"]


def test_duplicate_email_within_same_account_type_returns_409(client):
    email = "duplicate@example.com"
    password = "correct horse battery staple"

    first = client.post("/api/auth/guardian/register", json={"email": email, "password": password})
    assert first.status_code == 201

    second = client.post("/api/auth/guardian/register", json={"email": email, "password": password})
    assert second.status_code == 409
    assert second.json() == {"detail": "email_taken"}
