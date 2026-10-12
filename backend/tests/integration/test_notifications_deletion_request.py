"""Integration test: deletion-request confirmation emails (spec 045
US3, quickstart.md Scenario 4) -- self guardian/instructor, a
learner-target notifying the managing guardian instead of the learner,
no notification on a rejected duplicate, and the system/inactivity-
generated path also notifying.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import datetime
import uuid

import pytest

from src.models.enums import (
    AuthorizedByType,
    NotificationType,
    RetentionAccountType,
    RetentionEnrollmentStatus,
)
from src.models.notification_log_entry import NotificationLogEntry
from src.models.real_guardian_account import RealGuardianAccount
from src.models.retention_record import RetentionRecord
from src.services.deletion.inactivity import sweep_inactive_accounts

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    return TestClient(app, base_url="https://testserver")


def _register_guardian(client, email: str) -> str:
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correcthorse1"}
    )
    assert response.status_code == 201, response.text
    return response.json()["guardian_id"]


def _register_instructor(client, email: str) -> str:
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correcthorse1"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def test_guardian_self_deletion_request_notifies_the_guardian(client, db_session):
    guardian_id = _register_guardian(client, "self-delete-guardian@example.com")
    # Registration already logged one entry (US2) -- isolate the
    # deletion-confirmation row by notification_type below.

    response = client.post(
        "/api/deletion-requests", json={"target_type": "guardian", "target_id": guardian_id}
    )
    assert response.status_code == 201, response.text

    db_session.expire_all()
    entry = (
        db_session.query(NotificationLogEntry)
        .filter(
            NotificationLogEntry.notification_type == NotificationType.DELETION_REQUEST_CONFIRMATION
        )
        .one()
    )
    assert str(entry.account_id) == guardian_id
    assert entry.account_type == AuthorizedByType.GUARDIAN


def test_instructor_self_deletion_request_notifies_the_instructor(client, db_session):
    instructor_id = _register_instructor(client, "self-delete-instructor@example.com")

    response = client.post(
        "/api/deletion-requests", json={"target_type": "instructor", "target_id": instructor_id}
    )
    assert response.status_code == 201, response.text

    db_session.expire_all()
    entry = (
        db_session.query(NotificationLogEntry)
        .filter(
            NotificationLogEntry.notification_type == NotificationType.DELETION_REQUEST_CONFIRMATION
        )
        .one()
    )
    assert str(entry.account_id) == instructor_id
    assert entry.account_type == AuthorizedByType.INSTRUCTOR


def test_learner_deletion_request_notifies_the_guardian_not_the_learner(client, db_session):
    guardian_id = _register_guardian(client, "learner-owner@example.com")

    learner_response = client.post("/api/learners", json={"display_name": "Jamie"})
    assert learner_response.status_code == 201, learner_response.text
    learner_id = learner_response.json()["learner_id"]

    response = client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": learner_id}
    )
    assert response.status_code == 201, response.text

    db_session.expire_all()
    entry = (
        db_session.query(NotificationLogEntry)
        .filter(
            NotificationLogEntry.notification_type == NotificationType.DELETION_REQUEST_CONFIRMATION
        )
        .one()
    )
    assert str(entry.account_id) == guardian_id
    assert entry.account_type == AuthorizedByType.GUARDIAN


def test_duplicate_pending_deletion_request_sends_no_second_notification(client, db_session):
    guardian_id = _register_guardian(client, "dupe-delete-guardian@example.com")

    first = client.post(
        "/api/deletion-requests", json={"target_type": "guardian", "target_id": guardian_id}
    )
    assert first.status_code == 201

    second = client.post(
        "/api/deletion-requests", json={"target_type": "guardian", "target_id": guardian_id}
    )
    assert second.status_code == 409

    db_session.expire_all()
    count = (
        db_session.query(NotificationLogEntry)
        .filter(
            NotificationLogEntry.notification_type == NotificationType.DELETION_REQUEST_CONFIRMATION
        )
        .count()
    )
    assert count == 1


def test_inactivity_sweep_generated_request_also_notifies(db_session):
    guardian = RealGuardianAccount(
        email=f"inactive-guardian-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(guardian)
    db_session.commit()
    db_session.refresh(guardian)

    retention_record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=uuid.uuid4(),
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=guardian.guardian_id,
        enrollment_status=RetentionEnrollmentStatus.INACTIVE,
        became_inactive_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=400),
    )
    db_session.add(retention_record)
    db_session.commit()
    db_session.refresh(retention_record)

    from src.models.learner_profile import LearnerProfile

    learner = LearnerProfile(
        display_name="Inactive Learner",
        is_demo=False,
        guardian_id=guardian.guardian_id,
        retention_record_id=retention_record.retention_record_id,
    )
    db_session.add(learner)
    db_session.commit()
    db_session.refresh(learner)
    retention_record.account_id = learner.learner_id
    db_session.commit()

    created = sweep_inactive_accounts(db_session)
    assert created == 1

    db_session.expire_all()
    entry = (
        db_session.query(NotificationLogEntry)
        .filter(
            NotificationLogEntry.notification_type == NotificationType.DELETION_REQUEST_CONFIRMATION
        )
        .one()
    )
    assert str(entry.account_id) == str(guardian.guardian_id)
    assert entry.account_type == AuthorizedByType.GUARDIAN
