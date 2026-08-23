"""Integration test: instructor register/login/logout round trip; a
protected route rejects a missing/expired session (quickstart scenario
1, T016).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.services.auth.tokens import SESSION_COOKIE_NAME

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    # Hermetic: don't depend on the developer's/CI's shell actually
    # having JWT_SECRET exported -- these tests exercise the real
    # issue_token/verify_token path, not a mock.
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")

    # https base_url so the response's `Secure` cookie attribute is
    # actually stored/resent by httpx's cookie jar across requests on
    # this client -- the default "http://testserver" would silently
    # drop it (plan.md's Constraints require Secure in production).
    return TestClient(app, base_url="https://testserver")


def test_instructor_register_login_logout_round_trip(client):
    email = "teacher@example.com"
    password = "correct horse battery staple"

    register = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": password}
    )
    assert register.status_code == 201, register.text
    body = register.json()
    assert set(body.keys()) == {"instructor_id"}
    assert SESSION_COOKIE_NAME in client.cookies

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert SESSION_COOKIE_NAME not in client.cookies

    login = client.post("/api/auth/instructor/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    assert login.json() == {"instructor_id": body["instructor_id"]}
    assert SESSION_COOKIE_NAME in client.cookies


def test_instructor_login_wrong_password_returns_401(client):
    email = "teacher2@example.com"
    client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct-password"}
    )
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


def test_instructor_login_unknown_email_returns_401(client):
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


def test_protected_route_rejects_missing_session(client):
    """`/api/learners` (the only currently-registered session-protected
    route in this phase) with no session cookie at all -- proves the
    shared `_current_claims` gate rejects before any account-type check
    runs, independent of which of current_guardian/current_instructor a
    given route uses."""
    response = client.post("/api/learners", json={"display_name": "Jamie"})
    assert response.status_code == 401
    assert response.json() == {"detail": "not_authenticated"}


def test_protected_route_rejects_invalid_session(client):
    client.cookies.set(SESSION_COOKIE_NAME, "not-a-valid-jwt")
    response = client.post("/api/learners", json={"display_name": "Jamie"})
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_session"}
