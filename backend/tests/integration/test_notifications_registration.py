"""Integration test: registration-confirmation emails (spec 045 US2,
quickstart.md Scenario 3).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.enums import AuthorizedByType, NotificationStatus, NotificationType
from src.models.notification_log_entry import NotificationLogEntry

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    return TestClient(app, base_url="https://testserver")


def test_guardian_registration_logs_one_sent_or_failed_notification(client, db_session):
    response = client.post(
        "/api/auth/guardian/register",
        json={"email": "newguardian@example.com", "password": "correcthorse1"},
    )
    assert response.status_code == 201, response.text
    guardian_id = response.json()["guardian_id"]

    db_session.expire_all()
    entry = db_session.query(NotificationLogEntry).one()
    assert entry.notification_type == NotificationType.REGISTRATION
    assert entry.account_type == AuthorizedByType.GUARDIAN
    assert str(entry.account_id) == guardian_id
    assert entry.status in (NotificationStatus.SENT, NotificationStatus.FAILED)


def test_instructor_registration_logs_one_sent_or_failed_notification(client, db_session):
    response = client.post(
        "/api/auth/instructor/register",
        json={"email": "newinstructor@example.com", "password": "correcthorse1"},
    )
    assert response.status_code == 201, response.text
    instructor_id = response.json()["instructor_id"]

    db_session.expire_all()
    entry = db_session.query(NotificationLogEntry).one()
    assert entry.notification_type == NotificationType.REGISTRATION
    assert entry.account_type == AuthorizedByType.INSTRUCTOR
    assert str(entry.account_id) == instructor_id


def test_duplicate_registration_sends_no_second_notification(client, db_session):
    email = "dupe@example.com"
    first = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correcthorse1"}
    )
    assert first.status_code == 201

    second = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correcthorse1"}
    )
    assert second.status_code == 409

    db_session.expire_all()
    assert db_session.query(NotificationLogEntry).count() == 1
