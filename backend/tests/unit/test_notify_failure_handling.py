"""Unit tests: `backend/src/services/notifications/notify.py` (spec 045
FR-012/FR-013) -- a failed `mailer.send_email` call still writes exactly
one `NotificationLogEntry` row with `status=failed` and never raises.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid
from unittest.mock import patch

from src.models.enums import AuthorizedByType, NotificationStatus, NotificationType
from src.models.notification_log_entry import NotificationLogEntry
from src.services.notifications.notify import (
    notify_deletion_request,
    notify_password_reset,
    notify_registration,
)


def test_notify_registration_logs_failed_on_send_failure(db_session):
    account_id = uuid.uuid4()
    with patch("src.services.notifications.notify.send_email", return_value=False):
        notify_registration(
            db_session,
            is_demo=False,
            account_type=AuthorizedByType.GUARDIAN,
            account_id=account_id,
            email="someone@example.com",
        )

    entry = db_session.query(NotificationLogEntry).one()
    assert entry.notification_type == NotificationType.REGISTRATION
    assert entry.status == NotificationStatus.FAILED
    assert entry.error_detail is not None


def test_notify_password_reset_logs_failed_on_send_exception(db_session):
    """Even if `mailer.send_email` broke its own never-raises contract,
    `notify_*` must still not propagate (FR-012's bar is on the
    triggering action, not just the mailer's self-discipline)."""
    account_id = uuid.uuid4()
    with patch("src.services.notifications.notify.send_email", side_effect=RuntimeError("boom")):
        notify_password_reset(
            db_session,
            is_demo=False,
            account_type=AuthorizedByType.GUARDIAN,
            account_id=account_id,
            email="someone@example.com",
            reset_link="https://cognivo.example/guardian/reset-password?token=abc",
        )

    entry = db_session.query(NotificationLogEntry).one()
    assert entry.notification_type == NotificationType.PASSWORD_RESET
    assert entry.status == NotificationStatus.FAILED


def test_notify_deletion_request_logs_failed_on_send_failure(db_session):
    account_id = uuid.uuid4()
    with patch("src.services.notifications.notify.send_email", return_value=False):
        notify_deletion_request(
            db_session,
            is_demo=False,
            account_type=AuthorizedByType.INSTRUCTOR,
            account_id=account_id,
            email="someone@example.com",
            target_description="your account",
        )

    entry = db_session.query(NotificationLogEntry).one()
    assert entry.notification_type == NotificationType.DELETION_REQUEST_CONFIRMATION
    assert entry.status == NotificationStatus.FAILED


def test_demo_account_short_circuits_before_any_send_attempt(db_session):
    account_id = uuid.uuid4()
    with patch("src.services.notifications.notify.send_email") as mock_send:
        notify_registration(
            db_session,
            is_demo=True,
            account_type=AuthorizedByType.GUARDIAN,
            account_id=account_id,
            email="demo@example.com",
        )
    mock_send.assert_not_called()
    assert db_session.query(NotificationLogEntry).count() == 0
