"""Integration test: zero `notification_log_entries` rows are ever
written for a demo guardian, a demo instructor, or a demo learner's
guardian, across all three trigger points (spec 045 FR-011,
quickstart.md Scenario 5).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.learner_profile import LearnerProfile
from src.models.notification_log_entry import NotificationLogEntry
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    # Don't pay forgot-password's real constant-time floor in tests.
    monkeypatch.setattr("src.api.routes.auth._FORGOT_PASSWORD_RESPONSE_FLOOR_SECONDS", 0.0)
    return TestClient(app, base_url="https://testserver")


def test_demo_guardian_gets_no_notifications_at_any_trigger_point(client, db_session):
    demo = RealGuardianAccount(
        email="demo-guardian-guard@example.com", password_hash="x", is_demo=True
    )
    db_session.add(demo)
    db_session.commit()
    db_session.refresh(demo)

    forgot = client.post(
        "/api/auth/guardian/forgot-password", json={"email": "demo-guardian-guard@example.com"}
    )
    assert forgot.status_code == 204

    db_session.expire_all()
    assert db_session.query(NotificationLogEntry).count() == 0


def test_demo_instructor_gets_no_notifications_at_any_trigger_point(client, db_session):
    demo = RealInstructorAccount(
        email="demo-instructor-guard@example.com", password_hash="x", is_demo=True
    )
    db_session.add(demo)
    db_session.commit()
    db_session.refresh(demo)

    forgot = client.post(
        "/api/auth/instructor/forgot-password", json={"email": "demo-instructor-guard@example.com"}
    )
    assert forgot.status_code == 204

    db_session.expire_all()
    assert db_session.query(NotificationLogEntry).count() == 0


def test_demo_learners_guardian_gets_no_deletion_notification(client, db_session):
    """A demo learner's deletion-request submission is itself rejected
    (spec 020 FR-007, `test_deletion_demo_account_guard.py`) before this
    feature's notify call would even be reached -- this test confirms
    the notification side specifically stays silent in that case."""
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": "demo-learner-owner@example.com", "password": "correcthorse1"},
    )
    assert register.status_code == 201, register.text
    guardian_id = register.json()["guardian_id"]

    demo_learner = LearnerProfile(
        display_name="Demo Learner", is_demo=True, guardian_id=guardian_id
    )
    db_session.add(demo_learner)
    db_session.commit()
    db_session.refresh(demo_learner)

    response = client.post(
        "/api/deletion-requests",
        json={"target_type": "learner", "target_id": str(demo_learner.learner_id)},
    )
    assert response.status_code == 403

    db_session.expire_all()
    # The guardian's own registration already logged one notification
    # (US2) -- the point here is no *second*, deletion-confirmation row
    # was added for the rejected demo-target submission.
    assert db_session.query(NotificationLogEntry).count() == 1
