"""Integration test: `sweep_inactive_accounts`'s decoupled creation vs.
notification -- every overdue record gets its `DeletionRequest`
created the same run it's found (never bounded by
`INACTIVITY_SWEEP_MAX_PER_RUN`, so FR-010's 1-year retention ceiling
is never delayed by a mailer-availability cap), while only the
*notify* step is bounded per run and retried on a later one for
anything skipped.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import datetime
import uuid

import pytest

from src.models.deletion_request import DeletionRequest
from src.models.enums import (
    AuthorizedByType,
    DeletionTargetType,
    NotificationStatus,
    NotificationType,
    RetentionAccountType,
    RetentionEnrollmentStatus,
)
from src.models.notification_log_entry import NotificationLogEntry
from src.models.real_instructor_account import RealInstructorAccount
from src.models.retention_record import RetentionRecord
from src.services.deletion import inactivity

pytestmark = pytest.mark.usefixtures("database_available")


def _make_overdue_instructor(db_session, *, days_inactive: int = 400) -> RealInstructorAccount:
    instructor = RealInstructorAccount(
        email=f"overdue-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(instructor)
    db_session.commit()
    db_session.refresh(instructor)

    db_session.add(
        RetentionRecord(
            account_type=RetentionAccountType.INSTRUCTOR,
            account_id=instructor.instructor_id,
            authorized_by_type=AuthorizedByType.INSTRUCTOR,
            authorized_by_id=instructor.instructor_id,
            enrollment_status=RetentionEnrollmentStatus.INACTIVE,
            became_inactive_at=datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=days_inactive),
        )
    )
    db_session.commit()
    return instructor


def _notification_count(db_session, account_id: uuid.UUID) -> int:
    return (
        db_session.query(NotificationLogEntry)
        .filter(
            NotificationLogEntry.notification_type
            == NotificationType.DELETION_REQUEST_CONFIRMATION,
            NotificationLogEntry.account_id == account_id,
        )
        .count()
    )


def test_every_overdue_record_is_created_the_same_run_regardless_of_cap(db_session, monkeypatch):
    monkeypatch.setattr(inactivity, "INACTIVITY_SWEEP_MAX_PER_RUN", 2)

    first = _make_overdue_instructor(db_session, days_inactive=402)
    second = _make_overdue_instructor(db_session, days_inactive=401)
    third = _make_overdue_instructor(db_session, days_inactive=400)

    created = inactivity.sweep_inactive_accounts(db_session)
    assert created == 3

    db_session.expire_all()
    pending_ids = {
        row.target_id
        for row in db_session.query(DeletionRequest).filter(
            DeletionRequest.target_type == DeletionTargetType.INSTRUCTOR
        )
    }
    assert pending_ids == {first.instructor_id, second.instructor_id, third.instructor_id}


def test_notify_attempts_are_capped_and_retried_on_a_later_run(db_session, monkeypatch):
    monkeypatch.setattr(inactivity, "INACTIVITY_SWEEP_MAX_PER_RUN", 2)

    first = _make_overdue_instructor(db_session, days_inactive=402)
    second = _make_overdue_instructor(db_session, days_inactive=401)
    third = _make_overdue_instructor(db_session, days_inactive=400)

    inactivity.sweep_inactive_accounts(db_session)

    db_session.expire_all()
    assert _notification_count(db_session, first.instructor_id) == 1
    assert _notification_count(db_session, second.instructor_id) == 1
    # The cap (2) was already spent on first/second -- third's attempt
    # is deferred, not lost.
    assert _notification_count(db_session, third.instructor_id) == 0

    # DeletionRequest already exists for every record now (prior test's
    # own assertion), so this second run creates nothing new but must
    # still retry third's never-attempted notification.
    created_second_run = inactivity.sweep_inactive_accounts(db_session)
    assert created_second_run == 0

    db_session.expire_all()
    assert _notification_count(db_session, third.instructor_id) == 1


def test_an_already_notified_record_does_not_consume_cap_budget(db_session, monkeypatch):
    monkeypatch.setattr(inactivity, "INACTIVITY_SWEEP_MAX_PER_RUN", 1)

    already_handled = _make_overdue_instructor(db_session, days_inactive=402)
    deletion_request = DeletionRequest(
        target_type=DeletionTargetType.INSTRUCTOR,
        target_id=already_handled.instructor_id,
        requested_by="system:inactivity-sweep",
    )
    db_session.add(deletion_request)
    db_session.commit()
    db_session.add(
        NotificationLogEntry(
            notification_type=NotificationType.DELETION_REQUEST_CONFIRMATION,
            account_type=AuthorizedByType.INSTRUCTOR,
            account_id=already_handled.instructor_id,
            status=NotificationStatus.SENT,
        )
    )
    db_session.commit()

    fresh = _make_overdue_instructor(db_session, days_inactive=400)

    created = inactivity.sweep_inactive_accounts(db_session)
    assert created == 1  # only `fresh` -- `already_handled` already has a request

    db_session.expire_all()
    # The already-handled record's notify check was skipped as a free
    # (no-budget) no-op, leaving the single cap slot for the fresh one.
    assert _notification_count(db_session, already_handled.instructor_id) == 1
    assert _notification_count(db_session, fresh.instructor_id) == 1
