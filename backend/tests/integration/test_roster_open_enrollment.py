"""Integration test: open-roster creation and immediate guardian join
via code (quickstart scenario 3, T026).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.enrollment import Enrollment
from src.models.enums import AuthorizedByType

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client, email="teacher@example.com"):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _register_guardian_with_learner(client, email="parent@example.com", display_name="Jamie"):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def test_open_roster_creation_and_immediate_join(client, db_session, algebra_subject):
    _register_instructor(client)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    assert roster.status_code == 201, roster.text
    roster_body = roster.json()
    assert roster_body["enrollment_mode"] == "open"
    assert roster_body["join_code"] is not None
    roster_id = roster_body["roster_id"]

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)

    join = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": roster_body["join_code"]}
    )
    assert join.status_code == 201, join.text
    join_body = join.json()
    assert join_body["status"] == "enrolled"

    db_session.expire_all()
    enrollment = db_session.get(Enrollment, uuid.UUID(join_body["enrollment_id"]))
    assert enrollment is not None
    assert str(enrollment.roster_id) == roster_id
    assert str(enrollment.learner_id) == learner_id
    assert enrollment.authorized_by_type == AuthorizedByType.GUARDIAN


def test_closed_roster_create_response_still_includes_its_join_code(client, algebra_subject):
    """PR #28 review: the owning instructor must be able to learn a
    closed roster's own code (it's the only way they could ever share
    it with a guardian out of band) -- only a non-owner should never
    see it, and this response is always to the owner."""
    _register_instructor(client)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "closed"}
    )
    assert roster.status_code == 201, roster.text
    assert roster.json()["join_code"] is not None


def test_join_with_unknown_code_returns_404(client):
    _, learner_id = _register_guardian_with_learner(client)
    response = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": "NOPE-0000"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "invalid_join_code"}


def test_list_enrollments_reflects_enrolled_learners(client, algebra_subject):
    _register_instructor(client)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_id = roster.json()["roster_id"]
    join_code = roster.json()["join_code"]

    empty = client.get(f"/api/rosters/{roster_id}/enrollments")
    assert empty.status_code == 200
    assert empty.json() == {"enrollments": []}

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client)
    join = client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})
    assert join.status_code == 201, join.text

    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": "teacher@example.com", "password": "correct horse"},
    )
    assert response.status_code == 200

    listed = client.get(f"/api/rosters/{roster_id}/enrollments")
    assert listed.status_code == 200
    assert listed.json() == {"enrollments": [{"learner_id": learner_id, "display_name": "Jamie"}]}
