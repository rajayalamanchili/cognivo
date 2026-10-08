"""Integration tests: spec 043 instructor Settings backend --
`POST /api/auth/instructor/change-password` and the six new
`PATCH /api/auth/instructor/me` fields, mirroring
test_auth_guardian_settings.py's own coverage of the guardian
equivalents.

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


def _register_instructor(
    client, email="settings-instructor@example.com", password="correct horse battery staple"
):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _login_demo_instructor(client):
    seed_demo_instructor()
    client.get("/api/demo-instructor")


def test_change_instructor_password_success_and_relogin(client):
    email = "change-instructor-pw@example.com"
    old_password = "correct horse battery staple"
    new_password = "a different battery staple"
    _register_instructor(client, email=email, password=old_password)

    response = client.post(
        "/api/auth/instructor/change-password",
        json={"current_password": old_password, "new_password": new_password},
    )
    assert response.status_code == 204, response.text

    client.post("/api/auth/logout")
    old_login = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": old_password}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": new_password}
    )
    assert new_login.status_code == 200, new_login.text


def test_change_instructor_password_wrong_current_password_rejected(client):
    _register_instructor(
        client,
        email="wrong-current-instructor@example.com",
        password="correct horse battery staple",
    )
    response = client.post(
        "/api/auth/instructor/change-password",
        json={"current_password": "not the right password", "new_password": "a new password here"},
    )
    assert response.status_code == 401, response.text


def test_change_instructor_password_rejected_for_demo_account(client):
    _login_demo_instructor(client)
    response = client.post(
        "/api/auth/instructor/change-password",
        json={"current_password": "whatever", "new_password": "a new password here"},
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "demo_account"}


def test_change_instructor_password_locks_out_after_repeated_wrong_current_password(client):
    from src.services.auth.lockout import LOCKOUT_THRESHOLD

    email = "lockout-change-instructor-password@example.com"
    old_password = "correct horse battery staple"
    _register_instructor(client, email=email, password=old_password)

    for _ in range(LOCKOUT_THRESHOLD):
        attempt = client.post(
            "/api/auth/instructor/change-password",
            json={"current_password": "wrong password", "new_password": "a new password here"},
        )
        assert attempt.status_code == 401, attempt.text

    locked = client.post(
        "/api/auth/instructor/change-password",
        json={"current_password": old_password, "new_password": "a new password here"},
    )
    assert locked.status_code == 429, locked.text
    assert locked.json()["error"] == "rate_limited"


def test_patch_instructor_me_each_field_persists_independently(client):
    _register_instructor(client, email="instructor-prefs@example.com")

    theme_response = client.patch("/api/auth/instructor/me", json={"theme": "dark"})
    assert theme_response.status_code == 200, theme_response.text
    assert theme_response.json()["theme"] == "dark"

    larger_text_response = client.patch("/api/auth/instructor/me", json={"larger_text": True})
    assert larger_text_response.status_code == 200, larger_text_response.text
    body = larger_text_response.json()
    assert body["larger_text"] is True
    # Untouched fields keep their prior value -- exclude_unset semantics.
    assert body["theme"] == "dark"

    reduce_motion_response = client.patch("/api/auth/instructor/me", json={"reduce_motion": True})
    assert reduce_motion_response.json()["reduce_motion"] is True

    notifications_response = client.patch(
        "/api/auth/instructor/me", json={"notifications_enabled": False}
    )
    assert notifications_response.json()["notifications_enabled"] is False

    mode_response = client.patch(
        "/api/auth/instructor/me", json={"default_enrollment_mode": "closed"}
    )
    assert mode_response.json()["default_enrollment_mode"] == "closed"

    due_date_response = client.patch(
        "/api/auth/instructor/me", json={"default_due_date_offset_days": 7}
    )
    assert due_date_response.json()["default_due_date_offset_days"] == 7

    # Explicit null clears it back to "no due date by default".
    cleared_response = client.patch(
        "/api/auth/instructor/me", json={"default_due_date_offset_days": None}
    )
    assert cleared_response.json()["default_due_date_offset_days"] is None


def test_patch_instructor_me_default_due_date_offset_days_rejects_non_positive(client):
    _register_instructor(client, email="instructor-due-date-invalid@example.com")
    response = client.patch("/api/auth/instructor/me", json={"default_due_date_offset_days": 0})
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "default_due_date_offset_days_invalid"}

    negative = client.patch("/api/auth/instructor/me", json={"default_due_date_offset_days": -3})
    assert negative.status_code == 422, negative.text

    too_large = client.patch("/api/auth/instructor/me", json={"default_due_date_offset_days": 3651})
    assert too_large.status_code == 422, too_large.text


def test_patch_instructor_me_rejects_new_fields_for_demo_account(client):
    _login_demo_instructor(client)
    response = client.patch("/api/auth/instructor/me", json={"theme": "dark"})
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "demo_account"}


def test_patch_instructor_me_display_name_only_still_works_for_demo_account(client):
    _login_demo_instructor(client)
    response = client.patch("/api/auth/instructor/me", json={"display_name": "New Name"})
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "New Name"
