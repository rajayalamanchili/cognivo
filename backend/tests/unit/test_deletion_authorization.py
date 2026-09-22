"""Unit tests: `backend/src/services/deletion/authorization.py` (spec 020
FR-001, contracts/api.md's authorization table).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enums import AuthorizedByType, DeletionTargetType, EnrollmentMode
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.tokens import SessionClaims
from src.services.deletion.authorization import can_request_deletion


def _make_guardian(db_session) -> RealGuardianAccount:
    guardian = RealGuardianAccount(
        email=f"guardian-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(guardian)
    db_session.commit()
    db_session.refresh(guardian)
    return guardian


def _make_instructor(db_session) -> RealInstructorAccount:
    instructor = RealInstructorAccount(
        email=f"instructor-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(instructor)
    db_session.commit()
    db_session.refresh(instructor)
    return instructor


def _make_learner(db_session, *, guardian_id: uuid.UUID) -> LearnerProfile:
    learner = LearnerProfile(display_name="Test Learner", is_demo=False, guardian_id=guardian_id)
    db_session.add(learner)
    db_session.commit()
    db_session.refresh(learner)
    return learner


def _enroll(db_session, *, learner_id, instructor_id, subject_id) -> None:
    roster = ClassroomRoster(
        instructor_id=instructor_id, subject_id=subject_id, enrollment_mode=EnrollmentMode.CLOSED
    )
    db_session.add(roster)
    db_session.commit()
    db_session.refresh(roster)
    enrollment = Enrollment(
        learner_id=learner_id,
        roster_id=roster.roster_id,
        authorized_by_type=AuthorizedByType.INSTRUCTOR,
        authorized_by_id=instructor_id,
    )
    db_session.add(enrollment)
    db_session.commit()


def test_guardian_may_target_self(db_session):
    guardian = _make_guardian(db_session)
    claims = SessionClaims(account_type="guardian", account_id=guardian.guardian_id)

    assert can_request_deletion(
        claims, DeletionTargetType.GUARDIAN, guardian.guardian_id, db_session
    )


def test_guardian_may_target_own_linked_learner(db_session):
    guardian = _make_guardian(db_session)
    learner = _make_learner(db_session, guardian_id=guardian.guardian_id)
    claims = SessionClaims(account_type="guardian", account_id=guardian.guardian_id)

    assert can_request_deletion(claims, DeletionTargetType.LEARNER, learner.learner_id, db_session)


def test_guardian_may_not_target_unrelated_learner(db_session):
    guardian = _make_guardian(db_session)
    other_guardian = _make_guardian(db_session)
    other_learner = _make_learner(db_session, guardian_id=other_guardian.guardian_id)
    claims = SessionClaims(account_type="guardian", account_id=guardian.guardian_id)

    assert not can_request_deletion(
        claims, DeletionTargetType.LEARNER, other_learner.learner_id, db_session
    )


def test_guardian_may_not_target_an_instructor(db_session):
    guardian = _make_guardian(db_session)
    instructor = _make_instructor(db_session)
    claims = SessionClaims(account_type="guardian", account_id=guardian.guardian_id)

    assert not can_request_deletion(
        claims, DeletionTargetType.INSTRUCTOR, instructor.instructor_id, db_session
    )


def test_instructor_may_target_self(db_session):
    instructor = _make_instructor(db_session)
    claims = SessionClaims(account_type="instructor", account_id=instructor.instructor_id)

    assert can_request_deletion(
        claims, DeletionTargetType.INSTRUCTOR, instructor.instructor_id, db_session
    )


def test_instructor_may_target_learner_in_their_roster(db_session, algebra_subject):
    instructor = _make_instructor(db_session)
    guardian = _make_guardian(db_session)
    learner = _make_learner(db_session, guardian_id=guardian.guardian_id)
    _enroll(
        db_session,
        learner_id=learner.learner_id,
        instructor_id=instructor.instructor_id,
        subject_id=algebra_subject.subject_id,
    )
    claims = SessionClaims(account_type="instructor", account_id=instructor.instructor_id)

    assert can_request_deletion(claims, DeletionTargetType.LEARNER, learner.learner_id, db_session)


def test_instructor_may_not_target_learner_outside_their_rosters(db_session, algebra_subject):
    instructor = _make_instructor(db_session)
    other_instructor = _make_instructor(db_session)
    guardian = _make_guardian(db_session)
    learner = _make_learner(db_session, guardian_id=guardian.guardian_id)
    _enroll(
        db_session,
        learner_id=learner.learner_id,
        instructor_id=other_instructor.instructor_id,
        subject_id=algebra_subject.subject_id,
    )
    claims = SessionClaims(account_type="instructor", account_id=instructor.instructor_id)

    assert not can_request_deletion(
        claims, DeletionTargetType.LEARNER, learner.learner_id, db_session
    )


def test_demo_instructor_session_never_authorized(db_session):
    claims = SessionClaims(account_type="demo_instructor", account_id=uuid.uuid4())

    assert not can_request_deletion(
        claims, DeletionTargetType.INSTRUCTOR, claims.account_id, db_session
    )
