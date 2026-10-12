"""Unit tests: `backend/src/services/notifications/mailer.py` (spec 045
research.md §1; PR #115 review finding: `send_email` returns
`(success, failure_detail)`, not a bare `bool`, so a FAILED
`NotificationLogEntry` row can carry real debugging detail)."""

from unittest.mock import MagicMock, patch

import httpx

from src.services.notifications.mailer import send_email


def test_send_email_success_returns_no_failure_detail(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    response = MagicMock(is_success=True)
    with patch("httpx.post", return_value=response):
        sent, detail = send_email("to@example.com", "subject", "body")
    assert sent is True
    assert detail is None


def test_send_email_without_api_key_short_circuits_without_a_network_call(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    with patch("httpx.post") as mock_post:
        sent, detail = send_email("to@example.com", "subject", "body")
    mock_post.assert_not_called()
    assert sent is False
    assert detail == "RESEND_API_KEY/EMAIL_FROM_ADDRESS not configured"


def test_send_email_non_httperror_exception_is_still_caught(monkeypatch):
    """Review finding: only catching `httpx.HTTPError` let other
    exceptions (e.g. `UnicodeEncodeError` from a malformed header)
    escape and violate FR-012's "never raises"."""
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    with patch("httpx.post", side_effect=UnicodeEncodeError("ascii", "x", 0, 1, "bad")):
        sent, detail = send_email("to@example.com", "subject", "body")
    assert sent is False
    assert "UnicodeEncodeError" in detail


def test_send_email_non_2xx_returns_status_and_body(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    response = MagicMock(is_success=False, status_code=422, text="invalid recipient")
    with patch("httpx.post", return_value=response):
        sent, detail = send_email("to@example.com", "subject", "body")
    assert sent is False
    assert detail == "HTTP 422: invalid recipient"


def test_send_email_network_error_returns_exception_detail_and_never_raises(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    with patch("httpx.post", side_effect=httpx.ConnectTimeout("timed out")):
        sent, detail = send_email("to@example.com", "subject", "body")
    assert sent is False
    assert "ConnectTimeout" in detail


def test_send_email_redacts_recipient_address_echoed_in_provider_error(monkeypatch):
    """Review finding (PR #116): a provider error body can echo the
    recipient's address back verbatim (e.g. "invalid `to` address
    victim@example.com"), writing PII into `notification_log_entries`
    outside the account/retention path (Principle VIII)."""
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    response = MagicMock(
        is_success=False, status_code=422, text="invalid `to` address victim@example.com"
    )
    with patch("httpx.post", return_value=response):
        sent, detail = send_email("victim@example.com", "subject", "body")
    assert sent is False
    assert "victim@example.com" not in detail
    assert "[recipient email redacted]" in detail


def test_send_email_failure_detail_is_truncated(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    response = MagicMock(is_success=False, status_code=500, text="x" * 1000)
    with patch("httpx.post", return_value=response):
        _, detail = send_email("to@example.com", "subject", "body")
    assert len(detail) <= 200
