"""Integration tests: spec 041 FR-009/FR-011 guardian Settings backend --
`PATCH /api/auth/guardian/me`, `POST /api/auth/guardian/change-password`
(incl. its session-invalidation side effect, FR-022/research.md §6), and
`PATCH /api/learners/{learner_id}/practice-reminders-preference`.

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


def _register_guardian(client, email="settings-guardian@example.com", password="correct horse battery staple"):
    response = client.post("/api/auth/guardian/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()["guardian_id"]


def test_patch_guardian_me_updates_name_and_preferences(client):
    _register_guardian(client, email="me-update@example.com")

    response = client.patch(
        "/api/auth/guardian/me",
        json={"name": "Dana", "read_aloud_default": True, "theme": "dark"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Dana"
    assert body["read_aloud_default"] is True
    assert body["theme"] == "dark"
    assert body["email"] == "me-update@example.com"
    # Untouched fields keep their default.
    assert body["larger_text"] is False
    assert body["weekly_summary_enabled"] is False


def test_patch_guardian_me_omitted_fields_unchanged(client):
    _register_guardian(client, email="me-partial@example.com")
    client.patch("/api/auth/guardian/me", json={"weekly_summary_enabled": True})

    second = client.patch("/api/auth/guardian/me", json={"name": "Sam"})
    assert second.status_code == 200, second.text
    # weekly_summary_enabled wasn't in this second request -- must stay True.
    assert second.json()["weekly_summary_enabled"] is True
    assert second.json()["name"] == "Sam"


def test_patch_guardian_me_email_conflict(client):
    _register_guardian(client, email="taken@example.com")
    client.post("/api/auth/logout")
    _register_guardian(client, email="other@example.com")

    response = client.patch("/api/auth/guardian/me", json={"email": "taken@example.com"})
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "email_taken"}


def test_patch_guardian_me_rejects_explicit_null_email(client):
    """Claude Code Review finding on PR #109: `email` backs a NOT NULL
    column -- an explicit `null` must be rejected (422), not reach
    `_normalize_email(None)` and crash with an unhandled AttributeError."""
    _register_guardian(client, email="null-email@example.com")
    response = client.patch("/api/auth/guardian/me", json={"email": None})
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "email_required"}


def test_patch_guardian_me_rejects_explicit_null_boolean(client):
    """Same finding: a non-nullable boolean/theme field's explicit `null`
    must not reach `setattr` and trip the NOT NULL `IntegrityError`,
    which the handler below would otherwise misreport as `email_taken`."""
    _register_guardian(client, email="null-bool@example.com")
    response = client.patch("/api/auth/guardian/me", json={"read_aloud_default": None})
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "read_aloud_default_required"}


def test_patch_guardian_me_requires_guardian_session(client):
    client.post(
        "/api/auth/instructor/register",
        json={"email": "not-a-guardian@example.com", "password": "correct horse battery staple"},
    )
    response = client.patch("/api/auth/guardian/me", json={"name": "Dana"})
    assert response.status_code == 401, response.text


def test_change_password_success_and_relogin(client):
    email = "change-pw@example.com"
    old_password = "correct horse battery staple"
    new_password = "a different battery staple"
    _register_guardian(client, email=email, password=old_password)

    response = client.post(
        "/api/auth/guardian/change-password",
        json={"current_password": old_password, "new_password": new_password},
    )
    assert response.status_code == 204, response.text

    client.post("/api/auth/logout")
    old_login = client.post("/api/auth/guardian/login", json={"email": email, "password": old_password})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/guardian/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200, new_login.text


def test_change_password_wrong_current_password_rejected(client):
    _register_guardian(client, email="wrong-current@example.com", password="correct horse battery staple")
    response = client.post(
        "/api/auth/guardian/change-password",
        json={"current_password": "not the right password", "new_password": "a new password here"},
    )
    assert response.status_code == 401, response.text


def test_change_password_invalidates_prior_session_token(client, db_session):
    """FR-022/Edge Cases: a session cookie obtained *before* the change
    is rejected on its next use after the change; a cookie obtained
    *after* keeps working."""
    import time

    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.services.auth.tokens import SESSION_COOKIE_NAME

    email = "invalidate-session@example.com"
    old_password = "correct horse battery staple"
    _register_guardian(client, email=email, password=old_password)
    old_cookie = client.cookies[SESSION_COOKIE_NAME]

    # Ensure the new token's `iat` (whole seconds) is strictly later than
    # the old one's -- JWT `iat` has one-second resolution.
    time.sleep(1.1)

    client.post(
        "/api/auth/guardian/change-password",
        json={"current_password": old_password, "new_password": "a new password here"},
    )

    # The stale cookie is sent explicitly per-request (not stored in
    # `client`'s own jar, which already holds the still-valid post-
    # change cookie change-password's own response set) -- proves the
    # *old* token value itself is what's being rejected.
    stale_response = client.patch(
        "/api/auth/guardian/me",
        json={"name": "Stale"},
        cookies={SESSION_COOKIE_NAME: old_cookie},
    )
    assert stale_response.status_code == 401, stale_response.text

    # A separate client/cookie-jar logging in fresh (issued after the
    # change) keeps working.
    second_client = TestClient(app, base_url="https://testserver")
    second_client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "a new password here"}
    )
    fresh_response = second_client.patch("/api/auth/guardian/me", json={"name": "Fresh"})
    assert fresh_response.status_code == 200, fresh_response.text


def test_practice_reminders_preference_round_trip(client):
    _register_guardian(client, email="practice-reminders@example.com")
    learner = client.post("/api/learners", json={"display_name": "Eli"})
    learner_id = learner.json()["learner_id"]

    default = client.get(f"/api/learners/{learner_id}/practice-reminders-preference")
    assert default.status_code == 200, default.text
    assert default.json() == {"enabled": False}

    response = client.patch(
        f"/api/learners/{learner_id}/practice-reminders-preference", json={"enabled": True}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"enabled": True}

    off = client.patch(
        f"/api/learners/{learner_id}/practice-reminders-preference", json={"enabled": False}
    )
    assert off.json() == {"enabled": False}


def test_change_password_invalidates_prior_session_on_learner_scoped_route(client):
    """Claude Code Review finding on PR #109: `password_changed_at`
    revocation (FR-022) must also hold on learner-scoped routes gated
    by `require_learner_ownership_if_real` -- a stolen guardian session
    must stop reading a real learner's data on these routes too, not
    only on `current_guardian`-gated ones like `/api/auth/guardian/me`
    (`test_change_password_invalidates_prior_session_token` above)."""
    import time

    from fastapi.testclient import TestClient

    from src.api.main import app
    from src.services.auth.tokens import SESSION_COOKIE_NAME

    email = "invalidate-learner-route@example.com"
    old_password = "correct horse battery staple"
    _register_guardian(client, email=email, password=old_password)
    learner = client.post("/api/learners", json={"display_name": "Eli"})
    learner_id = learner.json()["learner_id"]
    old_cookie = client.cookies[SESSION_COOKIE_NAME]

    time.sleep(1.1)
    client.post(
        "/api/auth/guardian/change-password",
        json={"current_password": old_password, "new_password": "a new password here"},
    )

    stale_response = client.get(
        f"/api/learners/{learner_id}/practice-reminders-preference",
        cookies={SESSION_COOKIE_NAME: old_cookie},
    )
    assert stale_response.status_code == 403, stale_response.text

    second_client = TestClient(app, base_url="https://testserver")
    second_client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "a new password here"}
    )
    fresh_response = second_client.get(f"/api/learners/{learner_id}/practice-reminders-preference")
    assert fresh_response.status_code == 200, fresh_response.text


def test_practice_reminders_preference_requires_ownership(client):
    _register_guardian(client, email="owner@example.com")
    learner = client.post("/api/learners", json={"display_name": "Eli"})
    learner_id = learner.json()["learner_id"]
    client.post("/api/auth/logout")

    _register_guardian(client, email="not-the-owner@example.com")
    response = client.patch(
        f"/api/learners/{learner_id}/practice-reminders-preference", json={"enabled": True}
    )
    assert response.status_code == 403, response.text
