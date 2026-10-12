"""Integration test: guardian forgot-password/reset-password flow
(spec 045 quickstart.md Scenarios 1-2, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import datetime

import pytest

from src.models.enums import NotificationType
from src.models.notification_log_entry import NotificationLogEntry
from src.models.password_reset_token import PasswordResetToken
from src.models.real_guardian_account import RealGuardianAccount
from src.services.auth.tokens import SESSION_COOKIE_NAME

pytestmark = pytest.mark.usefixtures("database_available")

_RAW_TOKEN = "deterministic-test-raw-token-value"


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://cognivo.example")
    # No real RESEND_API_KEY -- the send fails, but the action and the
    # 204/200 responses below must be unaffected (FR-012).
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    # `reset_tokens.issue` never returns its raw token through the HTTP
    # response (only `token_hash` is ever persisted, by design) -- pin
    # the generator so tests can reconstruct it instead of needing to
    # intercept a real outbound email.
    monkeypatch.setattr(
        "src.services.auth.reset_tokens.secrets.token_urlsafe", lambda n: _RAW_TOKEN
    )
    # Don't pay forgot-password's real constant-time floor in tests.
    monkeypatch.setattr("src.api.routes.auth._FORGOT_PASSWORD_RESPONSE_FLOOR_SECONDS", 0.0)
    return TestClient(app, base_url="https://testserver")


def _register(client, email: str, password: str = "correct horse battery staple") -> str:
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    guardian_id = response.json()["guardian_id"]
    client.post("/api/auth/logout")
    return guardian_id


def test_forgot_password_issues_token_and_reset_completes_sign_in(client, db_session):
    email = "resetme@example.com"
    guardian_id = _register(client, email)

    forgot = client.post("/api/auth/guardian/forgot-password", json={"email": email})
    assert forgot.status_code == 204
    assert forgot.text == ""

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    assert str(token_row.account_id) == guardian_id

    reset = client.post(
        "/api/auth/guardian/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json() == {"guardian_id": guardian_id}
    assert SESSION_COOKIE_NAME in client.cookies

    client.post("/api/auth/logout")
    old_login = client.post(
        "/api/auth/guardian/login",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "newpassword123"}
    )
    assert new_login.status_code == 200

    db_session.expire_all()
    log_entry = (
        db_session.query(NotificationLogEntry)
        .filter(
            NotificationLogEntry.account_id == token_row.account_id,
            NotificationLogEntry.notification_type == NotificationType.PASSWORD_RESET,
        )
        .one()
    )
    assert log_entry.status.value == "failed"  # no real RESEND_API_KEY in this test


def test_reused_reset_token_is_rejected(client, db_session):
    email = "reuse@example.com"
    _register(client, email)
    client.post("/api/auth/guardian/forgot-password", json={"email": email})

    first = client.post(
        "/api/auth/guardian/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/auth/guardian/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "anotherpassword123"},
    )
    assert second.status_code == 422
    assert second.json() == {"detail": "reset_token_invalid"}


def test_expired_reset_token_is_rejected(client, db_session):
    email = "expired@example.com"
    _register(client, email)
    client.post("/api/auth/guardian/forgot-password", json={"email": email})

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    token_row.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1)
    db_session.commit()

    response = client.post(
        "/api/auth/guardian/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "reset_token_expired"}


def test_forgot_password_for_unknown_email_is_identical_204(client, db_session):
    response = client.post(
        "/api/auth/guardian/forgot-password", json={"email": "nosuchaccount@example.com"}
    )
    assert response.status_code == 204
    assert response.text == ""

    db_session.expire_all()
    assert db_session.query(PasswordResetToken).count() == 0


def test_forgot_password_for_demo_account_sends_nothing(client, db_session):
    demo = RealGuardianAccount(email="demoguardian@example.com", password_hash="x", is_demo=True)
    db_session.add(demo)
    db_session.commit()

    response = client.post(
        "/api/auth/guardian/forgot-password", json={"email": "demoguardian@example.com"}
    )
    assert response.status_code == 204

    db_session.expire_all()
    assert db_session.query(PasswordResetToken).count() == 0
    assert db_session.query(NotificationLogEntry).count() == 0


def test_concurrent_forgot_password_requests_do_not_duplicate_valid_tokens(client, db_session):
    """research.md §3: a second request within the 60s window is a
    silent no-op -- still 204, no second token issued."""
    email = "ratelimited@example.com"
    _register(client, email)

    first = client.post("/api/auth/guardian/forgot-password", json={"email": email})
    assert first.status_code == 204
    second = client.post("/api/auth/guardian/forgot-password", json={"email": email})
    assert second.status_code == 204

    db_session.expire_all()
    pending = db_session.query(PasswordResetToken).filter(PasswordResetToken.used_at.is_(None))
    assert pending.count() == 1
