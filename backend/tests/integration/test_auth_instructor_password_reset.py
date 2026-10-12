"""Integration test: instructor forgot-password/reset-password flow --
mirrors test_auth_guardian_password_reset.py exactly (spec 045
quickstart.md Scenarios 1-2, contracts/api.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import datetime

import pytest

from src.models.notification_log_entry import NotificationLogEntry
from src.models.password_reset_token import PasswordResetToken
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.tokens import SESSION_COOKIE_NAME

pytestmark = pytest.mark.usefixtures("database_available")

_RAW_TOKEN = "deterministic-test-raw-token-value"


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://cognivo.example")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.services.auth.reset_tokens.secrets.token_urlsafe", lambda n: _RAW_TOKEN
    )
    return TestClient(app, base_url="https://testserver")


def _register(client, email: str, password: str = "correct horse battery staple") -> str:
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    instructor_id = response.json()["instructor_id"]
    client.post("/api/auth/logout")
    return instructor_id


def test_forgot_password_issues_token_and_reset_completes_sign_in(client, db_session):
    email = "resetme-instructor@example.com"
    instructor_id = _register(client, email)

    forgot = client.post("/api/auth/instructor/forgot-password", json={"email": email})
    assert forgot.status_code == 204
    assert forgot.text == ""

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    assert str(token_row.account_id) == instructor_id

    reset = client.post(
        "/api/auth/instructor/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json() == {"instructor_id": instructor_id}
    assert SESSION_COOKIE_NAME in client.cookies

    client.post("/api/auth/logout")
    old_login = client.post(
        "/api/auth/instructor/login",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "newpassword123"}
    )
    assert new_login.status_code == 200


def test_reused_reset_token_is_rejected(client, db_session):
    email = "reuse-instructor@example.com"
    _register(client, email)
    client.post("/api/auth/instructor/forgot-password", json={"email": email})

    first = client.post(
        "/api/auth/instructor/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/auth/instructor/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "anotherpassword123"},
    )
    assert second.status_code == 422
    assert second.json() == {"detail": "reset_token_invalid"}


def test_expired_reset_token_is_rejected(client, db_session):
    email = "expired-instructor@example.com"
    _register(client, email)
    client.post("/api/auth/instructor/forgot-password", json={"email": email})

    db_session.expire_all()
    token_row = db_session.query(PasswordResetToken).one()
    token_row.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1)
    db_session.commit()

    response = client.post(
        "/api/auth/instructor/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "reset_token_expired"}


def test_forgot_password_for_unknown_email_is_identical_204(client, db_session):
    response = client.post(
        "/api/auth/instructor/forgot-password", json={"email": "nosuchaccount@example.com"}
    )
    assert response.status_code == 204
    assert response.text == ""

    db_session.expire_all()
    assert db_session.query(PasswordResetToken).count() == 0


def test_forgot_password_for_demo_account_sends_nothing(client, db_session):
    demo = RealInstructorAccount(
        email="demoinstructor2@example.com", password_hash="x", is_demo=True
    )
    db_session.add(demo)
    db_session.commit()

    response = client.post(
        "/api/auth/instructor/forgot-password", json={"email": "demoinstructor2@example.com"}
    )
    assert response.status_code == 204

    db_session.expire_all()
    assert db_session.query(PasswordResetToken).count() == 0
    assert db_session.query(NotificationLogEntry).count() == 0


def test_forgot_password_for_reserved_default_instructor_email_sends_nothing(
    client, db_session, monkeypatch
):
    """The seeded default instructor (spec 043) is a real, sign-in-able
    account with a well-known, documented email -- anyone could
    otherwise hijack it through this same public endpoint, the same
    way `register_instructor` already blocks squatting on it at
    signup."""
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", "default-instructor@example.com")
    default_instructor = RealInstructorAccount(
        email="default-instructor@example.com", password_hash="x", is_demo=False
    )
    db_session.add(default_instructor)
    db_session.commit()

    response = client.post(
        "/api/auth/instructor/forgot-password", json={"email": "default-instructor@example.com"}
    )
    assert response.status_code == 204

    db_session.expire_all()
    assert db_session.query(PasswordResetToken).count() == 0
    assert db_session.query(NotificationLogEntry).count() == 0


def test_guardian_token_is_not_accepted_on_instructor_reset_endpoint(client, db_session):
    """A reset token's `account_type` scopes which role's endpoint can
    consume it -- the two tables can share an email, and `token_hash` is
    globally unique across both, so this isn't implied for free."""
    from src.models.enums import AuthorizedByType
    from src.services.auth import reset_tokens as reset_tokens_service

    instructor_id = _register(client, "shared-role-test@example.com")

    # Issue a guardian-scoped token against this same account_id --
    # token_hash is globally unique across both roles' tokens, so this
    # exercises the account_type scoping, not an id collision.
    reset_tokens_service.issue(db_session, AuthorizedByType.GUARDIAN, instructor_id)
    response = client.post(
        "/api/auth/instructor/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "reset_token_invalid"}


def test_completing_a_reset_clears_an_existing_login_lockout(client, db_session):
    """A locked-out account is exactly US1's motivating case -- a
    completed reset must not leave it still locked out immediately
    afterward."""
    email = "lockedout-instructor@example.com"
    _register(client, email)

    for _ in range(5):  # LOCKOUT_THRESHOLD
        client.post(
            "/api/auth/instructor/login", json={"email": email, "password": "wrongpassword"}
        )
    locked_attempt = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "wrongpassword"}
    )
    assert locked_attempt.status_code == 429

    client.post("/api/auth/instructor/forgot-password", json={"email": email})
    reset = client.post(
        "/api/auth/instructor/reset-password",
        json={"token": _RAW_TOKEN, "new_password": "newpassword123"},
    )
    assert reset.status_code == 200, reset.text

    login = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "newpassword123"}
    )
    assert login.status_code == 200
