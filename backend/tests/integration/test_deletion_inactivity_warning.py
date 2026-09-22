"""Integration test: the 7-day pre-deletion warning appears via `GET
/api/auth/whoami` before any deletion occurs, clears on reactivation,
and never blocks or delays the actual deletion once the full 1-year
mark is reached (spec 020 Acceptance Scenario 4, FR-011, SC-006,
quickstart.md Scenario 2b).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime
import uuid

import pytest

from src.models.deletion_request import DeletionRequest
from src.models.enums import DeletionTargetType, RetentionEnrollmentStatus
from src.models.learner_profile import LearnerProfile
from src.models.retention_record import RetentionRecord

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    return TestClient(app, base_url="https://testserver")


def _register_guardian_with_learner(client) -> tuple[uuid.UUID, uuid.UUID]:
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert register.status_code == 201, register.text
    guardian_id = uuid.UUID(register.json()["guardian_id"])

    learner_response = client.post("/api/learners", json={"display_name": "Almost Warned"})
    assert learner_response.status_code == 201, learner_response.text
    learner_id = uuid.UUID(learner_response.json()["learner_id"])
    return guardian_id, learner_id


def _execute_cron(client) -> None:
    execute = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text


def test_warning_appears_before_deletion_and_clears_on_reactivation(client, db_session):
    _guardian_id, learner_id = _register_guardian_with_learner(client)
    learner = db_session.get(LearnerProfile, learner_id)
    retention_record_id = learner.retention_record_id

    db_session.query(RetentionRecord).filter(
        RetentionRecord.retention_record_id == retention_record_id
    ).update(
        {
            RetentionRecord.enrollment_status: RetentionEnrollmentStatus.INACTIVE,
            RetentionRecord.became_inactive_at: datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=360),
        }
    )
    db_session.commit()

    _execute_cron(client)

    whoami_response = client.get("/api/auth/whoami")
    assert whoami_response.status_code == 200, whoami_response.text
    warnings = whoami_response.json()["pending_deletion_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["target_type"] == "learner"
    assert warnings[0]["target_id"] == str(learner_id)

    expected_deletion_date = (
        (
            datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=360)
            + datetime.timedelta(days=365)
        )
        .date()
        .isoformat()
    )
    assert warnings[0]["scheduled_deletion_date"] == expected_deletion_date

    # No DeletionRequest exists yet -- the warning precedes the trigger.
    assert (
        db_session.query(DeletionRequest)
        .filter(
            DeletionRequest.target_type == DeletionTargetType.LEARNER,
            DeletionRequest.target_id == learner_id,
        )
        .count()
        == 0
    )

    # Reactivate: the warning clears on the next cron run.
    db_session.query(RetentionRecord).filter(
        RetentionRecord.retention_record_id == retention_record_id
    ).update({RetentionRecord.enrollment_status: RetentionEnrollmentStatus.ACTIVE})
    db_session.commit()

    _execute_cron(client)

    whoami_after = client.get("/api/auth/whoami")
    assert whoami_after.json()["pending_deletion_warnings"] == []


def test_warning_does_not_block_eventual_deletion(client, db_session):
    _guardian_id, learner_id = _register_guardian_with_learner(client)
    learner = db_session.get(LearnerProfile, learner_id)
    retention_record_id = learner.retention_record_id

    # Already past the full 1-year mark -- and, per the warning's own
    # design, past the 7-day-out warning threshold too.
    db_session.query(RetentionRecord).filter(
        RetentionRecord.retention_record_id == retention_record_id
    ).update(
        {
            RetentionRecord.enrollment_status: RetentionEnrollmentStatus.INACTIVE,
            RetentionRecord.became_inactive_at: datetime.datetime.now(datetime.UTC)
            - datetime.timedelta(days=400),
        }
    )
    db_session.commit()

    _execute_cron(client)

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
    assert request.completed_at is not None
    assert db_session.get(LearnerProfile, learner_id) is None
