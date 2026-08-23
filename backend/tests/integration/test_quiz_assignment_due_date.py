"""Integration test: due-date enforcement (contracts/api.md, FR-014,
T019).

A past `due_at` blocks a *new* `.../start` call with `409 past_due`,
but an already-in-progress attempt is never re-checked against
`due_at` on continuation (research.md §3: the check only ever runs at
the one moment it matters, someone attempting to *start*) -- an
assignment whose due date passes after a learner has already started
still lets them finish.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import datetime
import uuid

import pytest

from src.models.quiz_assignment import QuizAssignment
from tests.integration.quiz_assignment_helpers import (
    ENTRY_TOPIC,
    create_assignment,
    create_roster,
    join_roster,
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
def roster_and_learner(client, algebra_subject):
    register_instructor(client, "assign-due-instructor@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="assign-due-guardian@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    register_instructor(client, "assign-due-instructor@example.com")
    return roster_id, learner_id


def _login_guardian(client):
    response = client.post(
        "/api/auth/guardian/login",
        json={"email": "assign-due-guardian@example.com", "password": "correct horse"},
    )
    assert response.status_code == 200, response.text


def test_past_due_date_blocks_new_start(client, roster_and_learner):
    roster_id, learner_id = roster_and_learner
    past_due_at = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).isoformat()
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        due_at=past_due_at,
        learner_ids=[learner_id],
    )

    client.post("/api/auth/logout")
    _login_guardian(client)
    response = client.post(
        f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
    )
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "past_due"}


def test_in_progress_attempt_survives_due_date_passing(client, db_session, roster_and_learner):
    roster_id, learner_id = roster_and_learner
    future_due_at = (datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)).isoformat()
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        due_at=future_due_at,
        learner_ids=[learner_id],
    )

    client.post("/api/auth/logout")
    _login_guardian(client)
    with patch_generation():
        start = client.post(
            f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
        )
    assert start.status_code == 201, start.text
    quiz_session_id = start.json()["quiz_session_id"]
    question_id = start.json()["question"]["question_id"]

    # Simulate the due date having since passed on an already-started attempt.
    db_session.expire_all()
    db_assignment = db_session.get(QuizAssignment, uuid.UUID(assignment["assignment_id"]))
    db_assignment.due_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
    db_session.commit()

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    with patch_generation():
        next_question = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert next_question.status_code == 200, next_question.text
