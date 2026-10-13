"""Integration test: quiz-assignment create -> guardian completes ->
instructor per-learner report works identically for a new subject
(`chemistry`) as it does for Algebra I/Biology (spec 046 User Story 2,
SC-004, tasks.md T013).

Mirrors `test_quiz_assignment_new_subjects.py`'s exact setup/assertion
shape, scoped to a single learner/assignment against `chemistry` only
(spec.md's US2 Acceptance Scenarios name "a new subject" singular) --
deliberate scope choice matching Milestone 040's own precedent, not a
gap.
"""

import pytest

from tests.integration.quiz_assignment_helpers import (
    create_assignment,
    create_roster,
    join_roster,
    register_guardian_with_learner,
    register_instructor,
)
from tests.integration.quiz_helpers import patch_generation

pytestmark = pytest.mark.usefixtures("database_available")

_INSTRUCTOR_EMAIL = "chemistry-assign-instructor@example.com"
_GUARDIAN_EMAIL = "chemistry-assign-guardian@example.com"
_CHEMISTRY_ENTRY_TOPIC = "matter-and-measurement"


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _login_instructor(client):
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": _INSTRUCTOR_EMAIL, "password": "correct horse"},
    )
    assert response.status_code == 200, response.text


def _login_guardian(client):
    response = client.post(
        "/api/auth/guardian/login", json={"email": _GUARDIAN_EMAIL, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def test_chemistry_assignment_round_trip_matches_existing_subject_shape(
    client, chemistry_subject
):
    register_instructor(client, _INSTRUCTOR_EMAIL)
    roster_id, join_code = create_roster(client, subject_id="chemistry")

    client.post("/api/auth/logout")
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email=_GUARDIAN_EMAIL, learner_name="Chemistry Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    _login_instructor(client)
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[_CHEMISTRY_ENTRY_TOPIC],
        question_count=1,
        learner_ids=[learner_id],
    )
    assignment_id = assignment["assignment_id"]
    assert assignment["subject_id"] == "chemistry"

    client.post("/api/auth/logout")
    _login_guardian(client)
    with patch_generation():
        start = client.post(f"/api/assignments/{assignment_id}/learners/{learner_id}/start")
    assert start.status_code == 201, start.text
    answer = client.post(
        f"/api/questions/{start.json()['question']['question_id']}/answer",
        json={"response": 0},
    )
    assert answer.status_code == 200, answer.text

    client.post("/api/auth/logout")
    _login_instructor(client)
    report = client.get(f"/api/rosters/{roster_id}/assignments/{assignment_id}")
    assert report.status_code == 200, report.text
    learner_statuses = report.json()["learners"]
    assert len(learner_statuses) == 1
    assert learner_statuses[0]["learner_id"] == str(learner_id)
    assert learner_statuses[0]["status"] == "completed"
