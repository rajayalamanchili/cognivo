"""Integration test: single-attempt enforcement (contracts/api.md,
FR-014, T018).

A second `.../start` call for the same (assignment, learner) pair --
including a same-request-shape repeat that mirrors a double-click race
(`test_roster_duplicate_join.py`'s existing pattern for the comparable
duplicate-enrollment case) -- is rejected with `409 already_attempted`,
never a second `QuizSession`.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.quiz_session import QuizSession
from tests.integration.quiz_assignment_helpers import (
    ENTRY_TOPIC,
    create_assignment,
    create_roster,
    join_roster,
    login_instructor,
    register_guardian_with_learner,
    register_instructor,
)
from tests.integration.quiz_helpers import patch_generation

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def scenario(client, algebra_subject):
    register_instructor(client, "assign-single-instructor@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="assign-single-guardian@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    login_instructor(client, "assign-single-instructor@example.com")
    assignment = create_assignment(
        client, roster_id=roster_id, topic_ids=[ENTRY_TOPIC], learner_ids=[learner_id]
    )

    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/guardian/login",
        json={"email": "assign-single-guardian@example.com", "password": "correct horse"},
    )
    assert response.status_code == 200, response.text

    return {"assignment_id": assignment["assignment_id"], "learner_id": learner_id}


def test_second_start_rejected_with_already_attempted(client, db_session, scenario):
    with patch_generation():
        first = client.post(
            f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_id']}/start"
        )
    assert first.status_code == 201, first.text
    first_quiz_session_id = first.json()["quiz_session_id"]

    second = client.post(
        f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_id']}/start"
    )
    assert second.status_code == 409, second.text
    assert second.json() == {"detail": "already_attempted"}

    db_session.expire_all()
    sessions = (
        db_session.query(QuizSession)
        .filter(QuizSession.learner_id == uuid.UUID(scenario["learner_id"]))
        .all()
    )
    assert {str(s.quiz_session_id) for s in sessions} == {first_quiz_session_id}


def test_double_click_race_never_creates_two_sessions(client, db_session, scenario):
    """Mirrors `test_roster_duplicate_join.py`'s double-click pattern:
    two back-to-back requests for the same (assignment, learner) pair --
    only one may ever succeed, and the DB never ends up with two
    `QuizSession` rows for this target."""
    with patch_generation():
        first = client.post(
            f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_id']}/start"
        )
    with patch_generation():
        second = client.post(
            f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_id']}/start"
        )

    statuses = {first.status_code, second.status_code}
    assert statuses == {201, 409}

    db_session.expire_all()
    sessions = (
        db_session.query(QuizSession)
        .filter(QuizSession.learner_id == uuid.UUID(scenario["learner_id"]))
        .all()
    )
    assert len(sessions) == 1
