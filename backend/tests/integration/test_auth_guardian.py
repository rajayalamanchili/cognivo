"""Integration test: guardian register/login/logout + add a learner
profile, creating a `RetentionRecord` in the same transaction
(quickstart scenario 1, T017).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.enums import RetentionAccountType
from src.models.learner_profile import LearnerProfile
from src.models.retention_record import RetentionRecord
from src.services.auth.tokens import SESSION_COOKIE_NAME

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_guardian_register_login_logout_round_trip(client):
    email = "parent@example.com"
    password = "correct horse battery staple"

    register = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": password}
    )
    assert register.status_code == 201, register.text
    body = register.json()
    assert set(body.keys()) == {"guardian_id"}
    assert SESSION_COOKIE_NAME in client.cookies

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert SESSION_COOKIE_NAME not in client.cookies

    login = client.post("/api/auth/guardian/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    assert login.json() == {"guardian_id": body["guardian_id"]}
    assert SESSION_COOKIE_NAME in client.cookies


def test_guardian_adds_learner_profile_with_retention_record(client, db_session):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": "parent2@example.com", "password": "correct horse battery staple"},
    )
    guardian_id = register.json()["guardian_id"]

    response = client.post("/api/learners", json={"display_name": "Jamie"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["guardian_id"] == guardian_id
    learner_id = body["learner_id"]

    db_session.expire_all()
    learner = db_session.get(LearnerProfile, uuid.UUID(learner_id))
    assert learner is not None
    assert learner.display_name == "Jamie"
    assert learner.is_demo is False
    assert str(learner.guardian_id) == guardian_id
    assert learner.retention_record_id is not None

    retention_record = db_session.get(RetentionRecord, learner.retention_record_id)
    assert retention_record is not None
    assert retention_record.account_type == RetentionAccountType.LEARNER
    assert str(retention_record.account_id) == learner_id
    assert str(retention_record.authorized_by_id) == guardian_id
