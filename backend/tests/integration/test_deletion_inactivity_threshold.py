"""Integration test: the inactivity sweep only ever acts on a record
past the full 1-year ceiling -- a record inactive for less than a year,
or one that has returned to `active` (even with a stale
`became_inactive_at` left over from a prior inactive period), is left
untouched (spec 020 Acceptance Scenarios 2-3).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime
import uuid

from src.models.deletion_request import DeletionRequest
from src.models.enums import AuthorizedByType, RetentionAccountType, RetentionEnrollmentStatus
from src.models.retention_record import RetentionRecord
from src.services.deletion.inactivity import sweep_inactive_accounts


def _make_record(
    db_session, *, enrollment_status: RetentionEnrollmentStatus, became_inactive_at
) -> uuid.UUID:
    record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=uuid.uuid4(),
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=uuid.uuid4(),
        enrollment_status=enrollment_status,
        became_inactive_at=became_inactive_at,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record.account_id


def test_record_inactive_less_than_a_year_is_untouched(db_session):
    account_id = _make_record(
        db_session,
        enrollment_status=RetentionEnrollmentStatus.INACTIVE,
        became_inactive_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=200),
    )

    created = sweep_inactive_accounts(db_session)

    assert created == 0
    assert (
        db_session.query(DeletionRequest).filter(DeletionRequest.target_id == account_id).count()
        == 0
    )


def test_reactivated_record_with_stale_became_inactive_at_is_untouched(db_session):
    account_id = _make_record(
        db_session,
        enrollment_status=RetentionEnrollmentStatus.ACTIVE,
        became_inactive_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=400),
    )

    created = sweep_inactive_accounts(db_session)

    assert created == 0
    assert (
        db_session.query(DeletionRequest).filter(DeletionRequest.target_id == account_id).count()
        == 0
    )
