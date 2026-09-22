"""Integration test: running the inactivity sweep twice against the
same overdue `RetentionRecord` creates only one `DeletionRequest`, never
a duplicate (spec 020 FR-005).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime
import uuid

from src.models.deletion_request import DeletionRequest
from src.models.enums import AuthorizedByType, RetentionAccountType, RetentionEnrollmentStatus
from src.models.retention_record import RetentionRecord
from src.services.deletion.inactivity import sweep_inactive_accounts


def test_sweeping_twice_creates_only_one_deletion_request(db_session):
    account_id = uuid.uuid4()
    record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=account_id,
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=uuid.uuid4(),
        enrollment_status=RetentionEnrollmentStatus.INACTIVE,
        became_inactive_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=400),
    )
    db_session.add(record)
    db_session.commit()

    first_created = sweep_inactive_accounts(db_session)
    second_created = sweep_inactive_accounts(db_session)

    assert first_created == 1
    assert second_created == 0
    assert (
        db_session.query(DeletionRequest).filter(DeletionRequest.target_id == account_id).count()
        == 1
    )
