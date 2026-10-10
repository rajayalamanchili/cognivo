"""Integration test: `GET /api/learners/mine` -- spec 044 FR-001. A
learner enrolled in more than one roster must get all of them back, not
just the first one the underlying query happens to return (the
`ponytail:` gap `list_my_learners_route` previously documented).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from tests.integration.quiz_assignment_helpers import (
    create_roster,
    join_roster,
    register_guardian_with_learner,
    register_instructor,
)

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_returns_every_enrollment_for_a_learner_in_two_classes(
    client, algebra_subject, biology_subject
):
    register_instructor(client, "my-learners-algebra-teacher@example.com")
    algebra_roster_id, algebra_join_code = create_roster(
        client, subject_id=algebra_subject.subject_id
    )

    client.post("/api/auth/logout")
    register_instructor(client, "my-learners-biology-teacher@example.com")
    biology_roster_id, biology_join_code = create_roster(
        client, subject_id=biology_subject.subject_id
    )

    client.post("/api/auth/logout")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="my-learners-parent@example.com", learner_name="Multi Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=algebra_join_code)
    join_roster(client, learner_id=learner_id, join_code=biology_join_code)

    response = client.get("/api/learners/mine")

    assert response.status_code == 200, response.text
    [learner] = response.json()["learners"]
    assert learner["learner_id"] == learner_id
    roster_ids = {entry["roster_id"] for entry in learner["enrollments"]}
    assert roster_ids == {algebra_roster_id, biology_roster_id}


def test_empty_enrollments_list_for_a_learner_with_no_classes(client):
    register_guardian_with_learner(
        client,
        guardian_email="my-learners-unenrolled-parent@example.com",
        learner_name="Unenrolled Learner",
    )

    response = client.get("/api/learners/mine")

    assert response.status_code == 200, response.text
    [learner] = response.json()["learners"]
    assert learner["enrollments"] == []


def test_requires_a_guardian_session(client):
    response = client.get("/api/learners/mine")
    assert response.status_code == 401
