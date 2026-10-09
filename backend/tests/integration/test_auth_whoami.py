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
    assert response.json() == {
        "account_type": None,
        "identifier": None,
        "pending_deletion_warnings": [],
    }


def test_whoami_reports_guardian_session_with_email(client):
    client.post(
        "/api/auth/guardian/register",
        json={"email": "whoami-guardian@example.com", "password": "correct horse battery staple"},
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    # spec 041 FR-009/FR-011/FR-012: a guardian session now also carries
    # `guardian_id`, `name`, and the six Settings preference fields
    # (test_whoami_reports_guardian_preference_fields below covers
    # their values/persistence in full) -- every other account type's
    # shape is unchanged.
    body = response.json()
    guardian_id = body.pop("guardian_id")
    assert guardian_id
    assert body == {
        "account_type": "guardian",
        "identifier": "whoami-guardian@example.com",
        "pending_deletion_warnings": [],
        "name": None,
        "read_aloud_default": False,
        "larger_text": False,
        "reduce_motion": False,
        "theme": "system",
        "quiz_finished_email_enabled": True,
        "weekly_summary_enabled": False,
    }


def test_whoami_reports_instructor_session_with_email(client):
    """spec 043 contracts/api-changes.md §3: an instructor session now
    also carries the shared display fields (`theme`/`larger_text`/
    `reduce_motion`) plus the instructor-only preference fields --
    test_whoami_reports_instructor_preference_fields below covers their
    values/persistence in full."""
    client.post(
        "/api/auth/instructor/register",
        json={
            "email": "whoami-instructor@example.com",
            "password": "correct horse battery staple",
        },
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    body = response.json()
    instructor_id = body.pop("instructor_id")
    assert instructor_id
    assert body == {
        "account_type": "instructor",
        "identifier": "whoami-instructor@example.com",
        "pending_deletion_warnings": [],
        "name": None,
        "theme": "system",
        "larger_text": False,
        "reduce_motion": False,
        "notifications_enabled": True,
        "default_enrollment_mode": "open",
        "default_due_date_offset_days": None,
    }


def test_whoami_reports_demo_instructor_session_with_display_name(client):
    seeded = seed_demo_instructor()
    client.get("/api/demo-instructor")

    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "account_type": "demo_instructor",
        "identifier": seeded.display_name,
        "pending_deletion_warnings": [],
    }


def test_whoami_reports_guardian_preference_fields(client):
    """spec 041 FR-009/FR-011: `whoami` is Settings' single hydration
    read. Defaults match `data-model.md`'s column defaults before any
    `PATCH /api/auth/guardian/me` call."""
    client.post(
        "/api/auth/guardian/register",
        json={
            "email": "whoami-guardian-prefs@example.com",
            "password": "correct horse battery staple",
        },
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["account_type"] == "guardian"
    assert body["name"] is None
    assert body["read_aloud_default"] is False
    assert body["larger_text"] is False
    assert body["reduce_motion"] is False
    assert body["theme"] == "system"
    assert body["quiz_finished_email_enabled"] is True
    assert body["weekly_summary_enabled"] is False

    client.patch("/api/auth/guardian/me", json={"name": "Dana", "larger_text": True})
    updated = client.get("/api/auth/whoami").json()
    assert updated["name"] == "Dana"
    assert updated["larger_text"] is True


def test_whoami_reports_instructor_preference_fields(client):
    """spec 043: `whoami` is instructor Settings' single hydration read,
    same role it already plays for guardian Settings (spec 041).
    Defaults match data-model.md's column defaults before any
    `PATCH /api/auth/instructor/me` call; the fields must be absent
    (not merely null) for a guardian or demo-instructor session."""
    client.post(
        "/api/auth/instructor/register",
        json={
            "email": "whoami-instructor-prefs@example.com",
            "password": "correct horse battery staple",
        },
    )
    response = client.get("/api/auth/whoami")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["theme"] == "system"
    assert body["larger_text"] is False
    assert body["reduce_motion"] is False
    assert body["notifications_enabled"] is True
    assert body["default_enrollment_mode"] == "open"
    assert body["default_due_date_offset_days"] is None

    client.patch("/api/auth/instructor/me", json={"theme": "dark", "larger_text": True})
    updated = client.get("/api/auth/whoami").json()
    assert updated["theme"] == "dark"
    assert updated["larger_text"] is True


def test_whoami_instructor_only_fields_absent_for_guardian(client):
    client.post(
        "/api/auth/guardian/register",
        json={
            "email": "whoami-guardian-no-instructor-fields@example.com",
            "password": "correct horse battery staple",
        },
    )
    body = client.get("/api/auth/whoami").json()
    for field in (
        "instructor_id",
        "notifications_enabled",
        "default_enrollment_mode",
        "default_due_date_offset_days",
    ):
        assert field not in body


def test_whoami_instructor_only_fields_absent_for_demo_instructor(client):
    seeded = seed_demo_instructor()
    client.get("/api/demo-instructor")
    body = client.get("/api/auth/whoami").json()
    assert body["identifier"] == seeded.display_name
    for field in (
        "instructor_id",
        "name",
        "theme",
        "larger_text",
        "reduce_motion",
        "notifications_enabled",
        "default_enrollment_mode",
        "default_due_date_offset_days",
    ):
        assert field not in body


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
    assert response.json() == {
        "account_type": None,
        "identifier": None,
        "pending_deletion_warnings": [],
    }
