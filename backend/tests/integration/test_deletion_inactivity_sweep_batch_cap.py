"""Integration test: `sweep_inactive_accounts`'s per-run notify-attempt
cap (`INACTIVITY_SWEEP_MAX_PER_RUN`) -- bounds how many blocking
mailer calls one cron invocation makes, without letting an
already-pending (cheap-to-skip) record block progress toward ones
that still need creating.

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
    RetentionAccountType,
    RetentionEnrollmentStatus,
)
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


def test_sweep_stops_after_the_cap_and_resumes_next_run(db_session, monkeypatch):
    monkeypatch.setattr(inactivity, "INACTIVITY_SWEEP_MAX_PER_RUN", 2)

    # Oldest-overdue first -- days_inactive descending so ordering is
    # deterministic regardless of creation order.
    first = _make_overdue_instructor(db_session, days_inactive=402)
    second = _make_overdue_instructor(db_session, days_inactive=401)
    third = _make_overdue_instructor(db_session, days_inactive=400)

    created_first_run = inactivity.sweep_inactive_accounts(db_session)
    assert created_first_run == 2

    db_session.expire_all()
    pending_ids = {
        row.target_id
        for row in db_session.query(DeletionRequest).filter(
            DeletionRequest.target_type == DeletionTargetType.INSTRUCTOR
        )
    }
    assert pending_ids == {first.instructor_id, second.instructor_id}
    assert third.instructor_id not in pending_ids

    created_second_run = inactivity.sweep_inactive_accounts(db_session)
    assert created_second_run == 1

    db_session.expire_all()
    pending_ids = {
        row.target_id
        for row in db_session.query(DeletionRequest).filter(
            DeletionRequest.target_type == DeletionTargetType.INSTRUCTOR
        )
    }
    assert pending_ids == {first.instructor_id, second.instructor_id, third.instructor_id}


def test_already_pending_record_does_not_consume_the_cap_budget(db_session, monkeypatch):
    monkeypatch.setattr(inactivity, "INACTIVITY_SWEEP_MAX_PER_RUN", 1)

    stuck = _make_overdue_instructor(db_session, days_inactive=402)
    db_session.add(
        DeletionRequest(
            target_type=DeletionTargetType.INSTRUCTOR,
            target_id=stuck.instructor_id,
            requested_by="system:inactivity-sweep",
        )
    )
    db_session.commit()

    fresh = _make_overdue_instructor(db_session, days_inactive=400)

    created = inactivity.sweep_inactive_accounts(db_session)
    assert created == 1

    db_session.expire_all()
    fresh_request = (
        db_session.query(DeletionRequest)
        .filter(
            DeletionRequest.target_type == DeletionTargetType.INSTRUCTOR,
            DeletionRequest.target_id == fresh.instructor_id,
        )
        .one_or_none()
    )
    assert fresh_request is not None
