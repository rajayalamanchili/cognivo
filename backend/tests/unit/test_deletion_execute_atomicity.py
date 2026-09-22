"""Unit test: `backend/src/services/deletion/execute.py`'s
`execute_deletion` is all-or-nothing (spec 020 FR-003) -- a failure
partway through a cascade rolls back everything already deleted in that
same run and leaves the `DeletionRequest` pending, never partially
completed.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

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
from src.models.mastery_state import MasteryState
from src.models.real_guardian_account import RealGuardianAccount
from src.models.retention_record import RetentionRecord
from src.services.deletion.execute import execute_deletion


def _make_guardian(db_session) -> RealGuardianAccount:
    guardian = RealGuardianAccount(
        email=f"guardian-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(guardian)
    db_session.commit()
    db_session.refresh(guardian)
    return guardian


def test_failure_partway_through_cascade_rolls_back_and_leaves_request_pending(
    db_session, algebra_subject, monkeypatch
):
    guardian = _make_guardian(db_session)
    retention_record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=uuid.uuid4(),
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=guardian.guardian_id,
        enrollment_status=RetentionEnrollmentStatus.ACTIVE,
    )
    db_session.add(retention_record)
    db_session.commit()
    db_session.refresh(retention_record)

    learner = LearnerProfile(
        display_name="Test Learner",
        is_demo=False,
        guardian_id=guardian.guardian_id,
        retention_record_id=retention_record.retention_record_id,
    )
    db_session.add(learner)
    db_session.commit()
    db_session.refresh(learner)
    retention_record.account_id = learner.learner_id
    db_session.commit()

    topic = algebra_subject.topics[0]
    db_session.add(
        MasteryState(
            learner_id=learner.learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id=topic.topic_id,
            p_mastery=0.5,
        )
    )
    db_session.commit()

    learner_id = learner.learner_id

    deletion_request = DeletionRequest(
        target_type=DeletionTargetType.LEARNER, target_id=learner_id, requested_by="test"
    )
    db_session.add(deletion_request)
    db_session.commit()
    db_session.refresh(deletion_request)
    deletion_request_id = deletion_request.deletion_request_id

    original_query = db_session.query

    def failing_query(model, *args, **kwargs):
        if model is LearnerProfile:
            raise RuntimeError("simulated failure partway through the cascade")
        return original_query(model, *args, **kwargs)

    monkeypatch.setattr(db_session, "query", failing_query)

    with pytest.raises(RuntimeError, match="simulated failure"):
        execute_deletion(db_session, deletion_request)

    monkeypatch.undo()
    db_session.rollback()  # the session itself is left in an unusable state after the raise
    db_session.expunge_all()

    # Nothing from earlier in the cascade (mastery_states, deleted before
    # learner_profiles) was left partially removed.
    assert db_session.query(MasteryState).filter(MasteryState.learner_id == learner_id).count() == 1
    assert db_session.get(LearnerProfile, learner_id) is not None

    reloaded_request = db_session.get(DeletionRequest, deletion_request_id)
    assert reloaded_request.completed_at is None
