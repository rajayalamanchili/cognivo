"""Integration test: closed-roster join creates a pending request;
approve creates the `Enrollment` recording the instructor as
`authorized_by`; decline leaves the learner unenrolled (quickstart
scenario 4, T027).

A closed roster's `join_code` is deliberately hidden from the create/
PATCH API response (contracts/api.md) but still populated in the DB
(data-model.md's Correction, `POST /api/rosters/join` has no
`roster_id` field to target a roster any other way) -- this test reads
it directly via `db_session`, standing in for the out-of-band sharing a
real deployment would use.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enrollment_request import EnrollmentRequest
from src.models.enums import AuthorizedByType, EnrollmentDecision

pytestmark = pytest.mark.usefixtures("database_available")

_INSTRUCTOR_EMAIL = "teacher@example.com"
_INSTRUCTOR_PASSWORD = "correct horse"


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client) -> str:
    response = client.post(
        "/api/auth/instructor/register",
        json={"email": _INSTRUCTOR_EMAIL, "password": _INSTRUCTOR_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _sign_back_in_as_instructor(client) -> None:
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": _INSTRUCTOR_EMAIL, "password": _INSTRUCTOR_PASSWORD},
    )
    assert response.status_code == 200, response.text


def _register_guardian_with_learner(client, email="parent@example.com", display_name="Jamie"):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def _create_closed_roster_and_join_code(client, db_session, algebra_subject) -> tuple[str, str]:
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "closed"}
    )
    assert roster.status_code == 201, roster.text
    roster_id = roster.json()["roster_id"]
    assert roster.json()["join_code"] is None

    db_session.expire_all()
    roster_row = db_session.get(ClassroomRoster, uuid.UUID(roster_id))
    assert roster_row is not None and roster_row.join_code is not None
    return roster_id, roster_row.join_code


def test_closed_roster_approve_creates_enrollment(client, db_session, algebra_subject):
    instructor_id = _register_instructor(client)
    roster_id, join_code = _create_closed_roster_and_join_code(client, db_session, algebra_subject)

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    assert join.status_code == 202, join.text
    assert join.json()["status"] == "pending"
    request_id = join.json()["enrollment_request_id"]

    db_session.expire_all()
    assert (
        db_session.query(Enrollment).filter(Enrollment.roster_id == uuid.UUID(roster_id)).first()
        is None
    )

    client.post("/api/auth/logout")
    _sign_back_in_as_instructor(client)
    approve = client.post(f"/api/rosters/{roster_id}/requests/{request_id}/approve")
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
    enrollment_id = approve.json()["enrollment_id"]

    db_session.expire_all()
    enrollment = db_session.get(Enrollment, uuid.UUID(enrollment_id))
    assert enrollment is not None
    assert str(enrollment.learner_id) == learner_id
    assert str(enrollment.roster_id) == roster_id
    assert enrollment.authorized_by_type == AuthorizedByType.INSTRUCTOR
    assert str(enrollment.authorized_by_id) == instructor_id

    request_row = db_session.get(EnrollmentRequest, uuid.UUID(request_id))
    assert request_row.decision == EnrollmentDecision.APPROVED
    assert request_row.decided_at is not None


def test_closed_roster_decline_leaves_learner_unenrolled(client, db_session, algebra_subject):
    _register_instructor(client)
    roster_id, join_code = _create_closed_roster_and_join_code(client, db_session, algebra_subject)

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    request_id = join.json()["enrollment_request_id"]

    client.post("/api/auth/logout")
    _sign_back_in_as_instructor(client)
    decline = client.post(f"/api/rosters/{roster_id}/requests/{request_id}/decline")
    assert decline.status_code == 200, decline.text
    assert decline.json() == {"status": "declined"}

    db_session.expire_all()
    assert (
        db_session.query(Enrollment).filter(Enrollment.roster_id == uuid.UUID(roster_id)).first()
        is None
    )
    request_row = db_session.get(EnrollmentRequest, uuid.UUID(request_id))
    assert request_row.decision == EnrollmentDecision.DECLINED


def test_requests_list_only_shows_pending(client, db_session, algebra_subject):
    _register_instructor(client)
    roster_id, join_code = _create_closed_roster_and_join_code(client, db_session, algebra_subject)

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    request_id = join.json()["enrollment_request_id"]

    client.post("/api/auth/logout")
    _sign_back_in_as_instructor(client)

    before = client.get(f"/api/rosters/{roster_id}/requests")
    assert before.status_code == 200
    assert [r["enrollment_request_id"] for r in before.json()["requests"]] == [request_id]

    client.post(f"/api/rosters/{roster_id}/requests/{request_id}/approve")

    after = client.get(f"/api/rosters/{roster_id}/requests")
    assert after.status_code == 200
    assert after.json()["requests"] == []
