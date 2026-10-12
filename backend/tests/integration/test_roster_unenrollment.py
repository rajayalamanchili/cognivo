"""Integration test: unenrollment by the guardian and separately by the
owning instructor each remove only the `Enrollment` link -- the
learner's account/data are unaffected (quickstart scenario 5, SC-007,
T029).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.enrollment import Enrollment
from src.models.grade_progress import GradeProgress
from src.models.learner_profile import LearnerProfile
from src.models.mastery_state import MasteryState

pytestmark = pytest.mark.usefixtures("database_available")

_ENTRY_TOPIC = "integers-and-operations"


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _login_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def _register_guardian_with_learner(client, email, display_name="Jamie"):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def _create_open_roster(client, algebra_subject) -> tuple[str, str]:
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    assert roster.status_code == 201, roster.text
    return roster.json()["roster_id"], roster.json()["join_code"]


def _assert_unenrolled_but_learner_intact(
    db_session, roster_id: str, learner_id: str, display_name: str
):
    db_session.expire_all()
    assert (
        db_session.query(Enrollment)
        .filter(
            Enrollment.roster_id == uuid.UUID(roster_id),
            Enrollment.learner_id == uuid.UUID(learner_id),
        )
        .first()
        is None
    )
    learner = db_session.get(LearnerProfile, uuid.UUID(learner_id))
    assert learner is not None
    assert learner.display_name == display_name


def test_guardian_unenrolls_own_learner(client, db_session, algebra_subject):
    _register_instructor(client, "teacher1@example.com")
    roster_id, join_code = _create_open_roster(client, algebra_subject)

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client, "parent1@example.com")
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    assert join.status_code == 201, join.text

    delete = client.delete(f"/api/rosters/{roster_id}/enrollments/{learner_id}")
    assert delete.status_code == 204, delete.text

    _assert_unenrolled_but_learner_intact(db_session, roster_id, learner_id, "Jamie")


def test_instructor_unenrolls_learner_from_own_roster(client, db_session, algebra_subject):
    _register_instructor(client, "teacher2@example.com")
    roster_id, join_code = _create_open_roster(client, algebra_subject)

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client, "parent2@example.com")
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    assert join.status_code == 201, join.text

    client.post("/api/auth/logout")
    _login_instructor(client, "teacher2@example.com")
    delete = client.delete(f"/api/rosters/{roster_id}/enrollments/{learner_id}")
    assert delete.status_code == 204, delete.text

    _assert_unenrolled_but_learner_intact(db_session, roster_id, learner_id, "Jamie")


def test_unenroll_keeps_mastery_and_grade_progress_intact(client, db_session, algebra_subject):
    """spec 044 FR-036 (US7): removing an Enrollment row must not touch
    the learner's MasteryState/GradeProgress rows for that subject --
    neither table references Enrollment by FK, so `unenroll()` has no
    cascade to perform. `/speckit-analyze` finding F3: the pre-existing
    tests above only re-checked LearnerProfile survival; this closes the
    gap FR-036 names explicitly."""
    _register_instructor(client, "teacher4@example.com")
    roster_id, join_code = _create_open_roster(client, algebra_subject)

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client, "parent4@example.com")
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    assert join.status_code == 201, join.text

    db_session.add(
        MasteryState(
            learner_id=uuid.UUID(learner_id),
            subject_id=algebra_subject.subject_id,
            topic_id=_ENTRY_TOPIC,
            p_mastery=0.75,
            update_count=3,
            consecutive_mastered_observations=1,
        )
    )
    db_session.add(
        GradeProgress(
            learner_id=uuid.UUID(learner_id),
            subject_id=algebra_subject.subject_id,
            unlocked_grade=7,
        )
    )
    db_session.commit()

    delete = client.delete(f"/api/rosters/{roster_id}/enrollments/{learner_id}")
    assert delete.status_code == 204, delete.text

    db_session.expire_all()
    mastery = db_session.get(
        MasteryState, (uuid.UUID(learner_id), algebra_subject.subject_id, _ENTRY_TOPIC)
    )
    assert mastery is not None
    assert mastery.p_mastery == 0.75

    grade_progress = db_session.get(GradeProgress, (uuid.UUID(learner_id), algebra_subject.subject_id))
    assert grade_progress is not None
    assert grade_progress.unlocked_grade == 7


def test_unenroll_by_unrelated_guardian_returns_403(client, algebra_subject):
    _register_instructor(client, "teacher3@example.com")
    roster_id, join_code = _create_open_roster(client, algebra_subject)

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client, "parent3@example.com")
    client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})

    client.post("/api/auth/logout")
    _register_guardian_with_learner(
        client, "unrelated-parent@example.com", display_name="Not Jamie"
    )

    delete = client.delete(f"/api/rosters/{roster_id}/enrollments/{learner_id}")
    assert delete.status_code == 403
    assert delete.json() == {"detail": "not_learner_guardian"}
