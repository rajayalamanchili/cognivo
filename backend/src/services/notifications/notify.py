"""spec 045 research.md §5: one function per `NotificationType` member.
Each takes `is_demo` as a required keyword argument and returns
immediately -- no send, no log row -- if `True` (Constitution Principle
VIII/FR-011, enforced here rather than trusted to each call site). Each
calls `mailer.send_email`, then writes exactly one `NotificationLogEntry`
row on the caller's own `db` session and commits it. Never raises
(FR-012) -- a failed send is logged, not propagated.
"""

import uuid

from sqlalchemy.orm import Session

from src.models.enums import AuthorizedByType, NotificationStatus, NotificationType
from src.models.notification_log_entry import NotificationLogEntry
from src.services.notifications.mailer import send_email


def _notify(
    db: Session,
    *,
    is_demo: bool,
    notification_type: NotificationType,
    account_type: AuthorizedByType,
    account_id: uuid.UUID,
    email: str,
    subject: str,
    body: str,
) -> None:
    if is_demo:
        return
    try:
        sent, failure_detail = send_email(email, subject, body)
    except Exception as exc:  # noqa: BLE001 -- a failed send must never propagate (FR-012)
        sent, failure_detail = False, f"{type(exc).__name__}: {exc}"

    try:
        db.add(
            NotificationLogEntry(
                notification_type=notification_type,
                account_type=account_type,
                account_id=account_id,
                status=NotificationStatus.SENT if sent else NotificationStatus.FAILED,
                error_detail=None if sent else failure_detail,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 -- logging the attempt must never block the
        # caller either (FR-012 covers the whole function, not just the send):
        # a DB error here must not propagate out of register_guardian/
        # register_instructor/submit_deletion_request after their own commit
        # has already succeeded (which would surface as a 500 for an
        # already-created account), or abort the inactivity-sweep loop.
        db.rollback()


def notify_registration(
    db: Session,
    *,
    is_demo: bool,
    account_type: AuthorizedByType,
    account_id: uuid.UUID,
    email: str,
) -> None:
    role = "guardian" if account_type == AuthorizedByType.GUARDIAN else "instructor"
    _notify(
        db,
        is_demo=is_demo,
        notification_type=NotificationType.REGISTRATION,
        account_type=account_type,
        account_id=account_id,
        email=email,
        subject="Welcome to Cognivo",
        body=f"Your Cognivo {role} account has been created with this email address.",
    )


def notify_password_reset(
    db: Session,
    *,
    is_demo: bool,
    account_type: AuthorizedByType,
    account_id: uuid.UUID,
    email: str,
    reset_link: str,
) -> None:
    _notify(
        db,
        is_demo=is_demo,
        notification_type=NotificationType.PASSWORD_RESET,
        account_type=account_type,
        account_id=account_id,
        email=email,
        subject="Reset your Cognivo password",
        body=(
            "Follow this link to reset your Cognivo password. "
            f"It expires in one hour and can only be used once.\n\n{reset_link}"
        ),
    )


def notify_deletion_request(
    db: Session,
    *,
    is_demo: bool,
    account_type: AuthorizedByType,
    account_id: uuid.UUID,
    email: str,
    target_description: str,
) -> None:
    _notify(
        db,
        is_demo=is_demo,
        notification_type=NotificationType.DELETION_REQUEST_CONFIRMATION,
        account_type=account_type,
        account_id=account_id,
        email=email,
        subject="Cognivo deletion request received",
        body=f"A request to delete {target_description} has been accepted and is now pending.",
    )
