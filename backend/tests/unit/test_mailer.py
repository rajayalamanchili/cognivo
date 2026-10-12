"""Unit tests: `backend/src/services/notifications/mailer.py` (spec 045
research.md §1; PR #115 review finding: `send_email` returns
`(success, failure_detail)`, not a bare `bool`, so a FAILED
`NotificationLogEntry` row can carry real debugging detail)."""

from unittest.mock import MagicMock, patch

import httpx

from src.services.notifications.mailer import send_email


def test_send_email_success_returns_no_failure_detail():
    response = MagicMock(is_success=True)
    with patch("httpx.post", return_value=response):
        sent, detail = send_email("to@example.com", "subject", "body")
    assert sent is True
    assert detail is None


def test_send_email_non_2xx_returns_status_and_body():
    response = MagicMock(is_success=False, status_code=422, text="invalid recipient")
    with patch("httpx.post", return_value=response):
        sent, detail = send_email("to@example.com", "subject", "body")
    assert sent is False
    assert detail == "HTTP 422: invalid recipient"


def test_send_email_network_error_returns_exception_detail_and_never_raises():
    with patch("httpx.post", side_effect=httpx.ConnectTimeout("timed out")):
        sent, detail = send_email("to@example.com", "subject", "body")
    assert sent is False
    assert "ConnectTimeout" in detail


def test_send_email_failure_detail_is_truncated():
    response = MagicMock(is_success=False, status_code=500, text="x" * 1000)
    with patch("httpx.post", return_value=response):
        _, detail = send_email("to@example.com", "subject", "body")
    assert len(detail) <= 200
