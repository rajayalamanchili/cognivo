"""Integration test: an inactivity-overdue `RetentionRecord` is deleted
through the exact same cascade as an explicit request, via the cron
executor's sweep phase (spec 020 Acceptance Scenario 1, FR-005, SC-002).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
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
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.retention_record import RetentionRecord

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    return TestClient(app)


def _make_overdue_learner(db_session) -> uuid.UUID:
    guardian = RealGuardianAccount(
        email=f"guardian-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(guardian)
    db_session.commit()
    db_session.refresh(guardian)

    retention_record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=uuid.uuid4(),
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=guardian.guardian_id,
        enrollment_status=RetentionEnrollmentStatus.INACTIVE,
        became_inactive_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=400),
    )
    db_session.add(retention_record)
    db_session.commit()
    db_session.refresh(retention_record)

    learner = LearnerProfile(
        display_name="Overdue Learner",
        is_demo=False,
        guardian_id=guardian.guardian_id,
        retention_record_id=retention_record.retention_record_id,
    )
    db_session.add(learner)
    db_session.commit()
    db_session.refresh(learner)
    retention_record.account_id = learner.learner_id
    db_session.commit()

    return learner.learner_id


def test_overdue_record_is_swept_into_a_deletion_request_and_then_deleted(client, db_session):
    learner_id = _make_overdue_learner(db_session)

    execute = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text
    body = execute.json()
    assert body["swept_count"] >= 1

    db_session.expunge_all()

    request = (
        db_session.query(DeletionRequest)
        .filter(
            DeletionRequest.target_type == DeletionTargetType.LEARNER,
            DeletionRequest.target_id == learner_id,
        )
        .first()
    )
    assert request is not None
    assert request.requested_by == "system:inactivity-sweep"
    assert request.completed_at is not None
    assert db_session.get(LearnerProfile, learner_id) is None
