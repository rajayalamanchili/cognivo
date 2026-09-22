"""Unit tests: `backend/src/services/deletion/inactivity.py`'s
`reconcile_inactivity_warnings` (spec 020 FR-011, research.md R10).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime
import uuid

from src.models.enums import AuthorizedByType, RetentionAccountType, RetentionEnrollmentStatus
from src.models.retention_record import RetentionRecord
from src.services.deletion.inactivity import (
    INACTIVITY_RETENTION_PERIOD,
    WARNING_LEAD_TIME,
    reconcile_inactivity_warnings,
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _make_record(
    db_session,
    *,
    enrollment_status: RetentionEnrollmentStatus,
    became_inactive_at: datetime.datetime | None,
    inactivity_warning_sent_at: datetime.datetime | None = None,
) -> RetentionRecord:
    record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=uuid.uuid4(),
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=uuid.uuid4(),
        enrollment_status=enrollment_status,
        became_inactive_at=became_inactive_at,
        inactivity_warning_sent_at=inactivity_warning_sent_at,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def test_record_crossing_threshold_gets_warned_exactly_once(db_session):
    became_inactive_at = _now() - (
        INACTIVITY_RETENTION_PERIOD - WARNING_LEAD_TIME + datetime.timedelta(hours=1)
    )
    record = _make_record(
        db_session,
        enrollment_status=RetentionEnrollmentStatus.INACTIVE,
        became_inactive_at=became_inactive_at,
    )
    record_id = record.retention_record_id

    changed = reconcile_inactivity_warnings(db_session)
    db_session.expunge_all()

    assert changed == 1
    first_run = db_session.get(RetentionRecord, record_id)
    assert first_run.inactivity_warning_sent_at is not None
    first_timestamp = first_run.inactivity_warning_sent_at

    changed_again = reconcile_inactivity_warnings(db_session)
    db_session.expunge_all()

    assert changed_again == 0
    second_run = db_session.get(RetentionRecord, record_id)
    assert second_run.inactivity_warning_sent_at == first_timestamp


def test_record_not_yet_at_threshold_is_left_unwarned(db_session):
    became_inactive_at = _now() - datetime.timedelta(days=30)
    record = _make_record(
        db_session,
        enrollment_status=RetentionEnrollmentStatus.INACTIVE,
        became_inactive_at=became_inactive_at,
    )
    record_id = record.retention_record_id

    changed = reconcile_inactivity_warnings(db_session)
    db_session.expunge_all()

    assert changed == 0
    assert db_session.get(RetentionRecord, record_id).inactivity_warning_sent_at is None


def test_active_record_with_stale_warning_gets_cleared(db_session):
    record = _make_record(
        db_session,
        enrollment_status=RetentionEnrollmentStatus.ACTIVE,
        became_inactive_at=_now() - datetime.timedelta(days=400),
        inactivity_warning_sent_at=_now() - datetime.timedelta(days=1),
    )
    record_id = record.retention_record_id

    changed = reconcile_inactivity_warnings(db_session)
    db_session.expunge_all()

    assert changed == 1
    assert db_session.get(RetentionRecord, record_id).inactivity_warning_sent_at is None


def test_active_record_with_stale_became_inactive_at_is_never_warned(db_session):
    """The `enrollment_status = "inactive"` guard on the set branch must
    take precedence: a reactivated record's `became_inactive_at` can
    still satisfy the threshold arithmetic, but must never trigger a
    (re-)warning once the account is active again (research.md R10)."""
    record = _make_record(
        db_session,
        enrollment_status=RetentionEnrollmentStatus.ACTIVE,
        became_inactive_at=_now() - datetime.timedelta(days=400),
        inactivity_warning_sent_at=None,
    )
    record_id = record.retention_record_id

    changed = reconcile_inactivity_warnings(db_session)
    db_session.expunge_all()

    assert changed == 0
    assert db_session.get(RetentionRecord, record_id).inactivity_warning_sent_at is None
