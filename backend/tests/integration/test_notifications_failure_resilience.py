"""Integration test: with `mailer.send_email` mocked to fail, every one
of the three trigger-point HTTP actions still returns its normal
success response (spec 045 SC-006, /speckit-analyze finding E1).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("FRONTEND_BASE_URL", "https://cognivo.example")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _failing_mailer():
    # `notify.py` imports `send_email` by name (`from ...mailer import
    # send_email`), so the patch target is its own module's binding, not
    # `mailer.send_email` itself.
    with patch("src.services.notifications.notify.send_email", side_effect=RuntimeError("down")):
        yield


def test_guardian_registration_succeeds_despite_email_failure(client):
    response = client.post(
        "/api/auth/guardian/register",
        json={"email": "resilient-guardian@example.com", "password": "correcthorse1"},
    )
    assert response.status_code == 201, response.text


def test_instructor_registration_succeeds_despite_email_failure(client):
    response = client.post(
        "/api/auth/instructor/register",
        json={"email": "resilient-instructor@example.com", "password": "correcthorse1"},
    )
    assert response.status_code == 201, response.text


def test_guardian_forgot_password_succeeds_despite_email_failure(client):
    client.post(
        "/api/auth/guardian/register",
        json={"email": "resilient-reset-guardian@example.com", "password": "correcthorse1"},
    )
    response = client.post(
        "/api/auth/guardian/forgot-password",
        json={"email": "resilient-reset-guardian@example.com"},
    )
    assert response.status_code == 204, response.text


def test_instructor_forgot_password_succeeds_despite_email_failure(client):
    client.post(
        "/api/auth/instructor/register",
        json={"email": "resilient-reset-instructor@example.com", "password": "correcthorse1"},
    )
    response = client.post(
        "/api/auth/instructor/forgot-password",
        json={"email": "resilient-reset-instructor@example.com"},
    )
    assert response.status_code == 204, response.text


def test_submit_deletion_request_succeeds_despite_email_failure(client):
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": "resilient-deletion-guardian@example.com", "password": "correcthorse1"},
    )
    guardian_id = register.json()["guardian_id"]

    response = client.post(
        "/api/deletion-requests", json={"target_type": "guardian", "target_id": guardian_id}
    )
    assert response.status_code == 201, response.text
