"""Integration test: a client-supplied `is_demo: true` in the register
request body is rejected or ignored -- the created account always has
`is_demo: false` (quickstart scenario 9, FR-016, SC-004, T019).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_guardian_register_ignores_client_supplied_is_demo(client, db_session):
    response = client.post(
        "/api/auth/guardian/register",
        json={"email": "sneaky-guardian@example.com", "password": "correct horse", "is_demo": True},
    )
    assert response.status_code == 201, response.text

    db_session.expire_all()
    guardian = db_session.get(RealGuardianAccount, uuid.UUID(response.json()["guardian_id"]))
    assert guardian is not None
    assert guardian.is_demo is False


def test_instructor_register_ignores_client_supplied_is_demo(client, db_session):
    response = client.post(
        "/api/auth/instructor/register",
        json={
            "email": "sneaky-instructor@example.com",
            "password": "correct horse",
            "is_demo": True,
        },
    )
    assert response.status_code == 201, response.text

    db_session.expire_all()
    instructor = db_session.get(RealInstructorAccount, uuid.UUID(response.json()["instructor_id"]))
    assert instructor is not None
    assert instructor.is_demo is False
