"""Integration test: instructor deletion resolves each owned roster
either by transfer (successor keeps the roster and its assignments,
enrolled learners untouched) or by deletion (roster and its roster-
scoped assignments removed, enrolled learners still untouched) -- spec
020 Acceptance Scenario 3, FR-008, SC-004.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

import pytest

from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enums import AuthorizedByType, EnrollmentMode
from src.models.learner_profile import LearnerProfile
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.models.real_instructor_account import RealInstructorAccount

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def second_client(client):
    """A separate cookie jar (same app/DB) for a second logged-in
    instructor -- registering a second account on `client` itself would
    silently swap out the first instructor's session cookie."""
    from fastapi.testclient import TestClient

    from src.api.main import app

    return TestClient(app, base_url="https://testserver")


def _register_instructor(client) -> uuid.UUID:
    response = client.post(
        "/api/auth/instructor/register",
        json={"email": f"instructor-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["instructor_id"])


def _seed_roster_with_learner_and_assignment(db_session, *, instructor_id, subject_id, topic_id):
    roster = ClassroomRoster(
        instructor_id=instructor_id, subject_id=subject_id, enrollment_mode=EnrollmentMode.OPEN
    )
    db_session.add(roster)
    db_session.commit()
    db_session.refresh(roster)

    learner = LearnerProfile(display_name="Enrolled Learner", is_demo=False)
    db_session.add(learner)
    db_session.commit()
    db_session.refresh(learner)

    db_session.add(
        Enrollment(
            learner_id=learner.learner_id,
            roster_id=roster.roster_id,
            authorized_by_type=AuthorizedByType.INSTRUCTOR,
            authorized_by_id=instructor_id,
        )
    )
    assignment = QuizAssignment(
        roster_id=roster.roster_id,
        instructor_id=instructor_id,
        subject_id=subject_id,
        topic_ids=[topic_id],
        question_count=5,
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    db_session.add(
        QuizAssignmentTarget(assignment_id=assignment.assignment_id, learner_id=learner.learner_id)
    )
    db_session.commit()

    return roster, learner, assignment


def test_instructor_deletion_with_transfer_preserves_roster_and_assignment(
    client, second_client, db_session, algebra_subject
):
    instructor_id = _register_instructor(client)
    successor_id = _register_instructor(second_client)
    roster, learner, assignment = _seed_roster_with_learner_and_assignment(
        db_session,
        instructor_id=instructor_id,
        subject_id=algebra_subject.subject_id,
        topic_id=algebra_subject.topics[0].topic_id,
    )
    roster_id = roster.roster_id
    learner_id = learner.learner_id
    assignment_id = assignment.assignment_id

    submit = client.post(
        "/api/deletion-requests",
        json={
            "target_type": "instructor",
            "target_id": str(instructor_id),
            "transfer_rosters_to": str(successor_id),
        },
    )
    assert submit.status_code == 201, submit.text

    execute = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text

    db_session.expunge_all()

    assert db_session.get(RealInstructorAccount, instructor_id) is None

    reloaded_roster = db_session.get(ClassroomRoster, roster_id)
    assert reloaded_roster is not None
    assert reloaded_roster.instructor_id == successor_id

    reloaded_assignment = db_session.get(QuizAssignment, assignment_id)
    assert reloaded_assignment is not None
    assert reloaded_assignment.instructor_id == successor_id

    assert db_session.get(LearnerProfile, learner_id) is not None
    assert db_session.query(Enrollment).filter(Enrollment.learner_id == learner_id).count() == 1


def test_instructor_deletion_without_successor_deletes_roster_not_learner(
    client, db_session, algebra_subject
):
    instructor_id = _register_instructor(client)
    roster, learner, assignment = _seed_roster_with_learner_and_assignment(
        db_session,
        instructor_id=instructor_id,
        subject_id=algebra_subject.subject_id,
        topic_id=algebra_subject.topics[0].topic_id,
    )
    roster_id = roster.roster_id
    learner_id = learner.learner_id
    assignment_id = assignment.assignment_id

    submit = client.post(
        "/api/deletion-requests",
        json={"target_type": "instructor", "target_id": str(instructor_id)},
    )
    assert submit.status_code == 201, submit.text

    execute = client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text

    db_session.expunge_all()

    assert db_session.get(RealInstructorAccount, instructor_id) is None
    assert db_session.get(ClassroomRoster, roster_id) is None
    assert db_session.get(QuizAssignment, assignment_id) is None
    assert (
        db_session.query(QuizAssignmentTarget)
        .filter(QuizAssignmentTarget.assignment_id == assignment_id)
        .count()
        == 0
    )
    assert db_session.query(Enrollment).filter(Enrollment.roster_id == roster_id).count() == 0

    # The enrolled learner's own account is never a side effect of the
    # instructor's deletion (FR-008).
    assert db_session.get(LearnerProfile, learner_id) is not None


def test_instructor_deletion_rejects_unknown_successor(client, db_session, algebra_subject):
    """A nonexistent `transfer_rosters_to` must be rejected before any
    roster is touched -- `classroom_rosters.instructor_id` carries no FK,
    so without this check the roster would be silently orphaned to a
    dead id instead of failing loudly."""
    instructor_id = _register_instructor(client)
    roster, _learner, _assignment = _seed_roster_with_learner_and_assignment(
        db_session,
        instructor_id=instructor_id,
        subject_id=algebra_subject.subject_id,
        topic_id=algebra_subject.topics[0].topic_id,
    )
    roster_id = roster.roster_id

    submit = client.post(
        "/api/deletion-requests",
        json={
            "target_type": "instructor",
            "target_id": str(instructor_id),
            "transfer_rosters_to": str(uuid.uuid4()),
        },
    )
    assert submit.status_code == 404, submit.text

    db_session.expunge_all()
    reloaded_roster = db_session.get(ClassroomRoster, roster_id)
    assert reloaded_roster is not None
    assert reloaded_roster.instructor_id == instructor_id
