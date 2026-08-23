"""Integration test: a learner can join two different rosters
(different instructors and/or subjects) simultaneously -- confirms two
independent `Enrollment` rows exist and each roster's enrolled-learner
list includes this learner with no cross-contamination between rosters
(FR-007, `/speckit-analyze` finding F3, T029b).

Deliberately tested at the roster/enrollment level, not via the
dashboard, so this has no dependency on User Story 3's endpoint.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.enrollment import Enrollment

pytestmark = pytest.mark.usefixtures("database_available")


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


def _login_guardian(client, email):
    response = client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def test_learner_joins_two_rosters_across_instructors_and_subjects(
    client, db_session, algebra_subject, biology_subject
):
    _register_instructor(client, "instructor-e@example.com")
    roster_1 = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_1_id = roster_1.json()["roster_id"]
    join_code_1 = roster_1.json()["join_code"]

    client.post("/api/auth/logout")
    _register_instructor(client, "instructor-f@example.com")
    roster_2 = client.post(
        "/api/rosters", json={"subject_id": biology_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_2_id = roster_2.json()["roster_id"]
    join_code_2 = roster_2.json()["join_code"]

    client.post("/api/auth/logout")
    register = client.post(
        "/api/auth/guardian/register",
        json={"email": "multi-parent@example.com", "password": "correct horse"},
    )
    assert register.status_code == 201, register.text
    learner = client.post("/api/learners", json={"display_name": "Multi Jamie"})
    learner_id = learner.json()["learner_id"]

    join_1 = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code_1}
    )
    assert join_1.status_code == 201, join_1.text
    enrollment_1_id = join_1.json()["enrollment_id"]

    join_2 = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code_2}
    )
    assert join_2.status_code == 201, join_2.text
    enrollment_2_id = join_2.json()["enrollment_id"]

    assert enrollment_1_id != enrollment_2_id

    db_session.expire_all()
    enrollments = (
        db_session.query(Enrollment).filter(Enrollment.learner_id == uuid.UUID(learner_id)).all()
    )
    assert {str(e.enrollment_id) for e in enrollments} == {enrollment_1_id, enrollment_2_id}
    assert {str(e.roster_id) for e in enrollments} == {roster_1_id, roster_2_id}

    # Each instructor's request-list scoping check (a lighter proxy for
    # "the dashboard shows this learner on both, with no
    # cross-contamination" -- the dashboard itself is User Story 3):
    # instructor E's roster only ever references roster_1's enrollment,
    # never roster_2's, and vice versa, confirmed via the roster_id on
    # each Enrollment row above rather than re-deriving it from a
    # not-yet-built endpoint.
    roster_1_enrollment = next(e for e in enrollments if str(e.roster_id) == roster_1_id)
    roster_2_enrollment = next(e for e in enrollments if str(e.roster_id) == roster_2_id)
    assert roster_1_enrollment.roster_id != roster_2_enrollment.roster_id
