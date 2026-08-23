"""Integration test: cancellation semantics (contracts/api.md, FR-012,
FR-016, T022; quickstart.md scenarios 5, 7).

Cancellation never retracts a completed attempt's recorded mastery
data; a cancelled assignment stays visible (marked cancelled, not
omitted) in the guardian's list regardless of the underlying attempt's
own status; and an attempt already in progress at cancellation time is
left alone -- it still reports `completed` with a real score once the
learner finishes it, cancellation only ever blocks a *new* start.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

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
def roster(client, algebra_subject):
    register_instructor(client, "assign-cancel-instructor@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)
    client.post("/api/auth/logout")
    return roster_id, join_code


def _register_and_join(client, roster, *, guardian_email, learner_name):
    roster_id, join_code = roster
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email=guardian_email, learner_name=learner_name
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)
    return learner_id


def _login_instructor(client):
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": "assign-cancel-instructor@example.com", "password": "correct horse"},
    )
    assert response.status_code == 200, response.text


def _login_guardian(client, email):
    response = client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def _assignment_entry(client, *, learner_id, assignment_id):
    response = client.get(f"/api/learners/{learner_id}/assignments")
    assert response.status_code == 200, response.text
    return next(a for a in response.json()["assignments"] if a["assignment_id"] == assignment_id)


def test_cancellation_leaves_completed_attempt_mastery_untouched(client, roster, algebra_subject):
    learner_id = _register_and_join(
        client, roster, guardian_email="assign-cancel-guardian-a@example.com", learner_name="A"
    )
    roster_id, _join_code = roster

    _login_instructor(client)
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        question_count=1,
        learner_ids=[learner_id],
    )

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-cancel-guardian-a@example.com")
    with patch_generation():
        start = client.post(
            f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
        )
    assert start.status_code == 201, start.text
    question_id = start.json()["question"]["question_id"]
    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    mastery_before = client.get(
        f"/api/learners/{learner_id}/mastery-state?subject_id={algebra_subject.subject_id}"
    ).json()

    client.post("/api/auth/logout")
    _login_instructor(client)
    cancel = client.delete(f"/api/rosters/{roster_id}/assignments/{assignment['assignment_id']}")
    assert cancel.status_code == 204, cancel.text

    mastery_after = client.get(
        f"/api/learners/{learner_id}/mastery-state?subject_id={algebra_subject.subject_id}"
    ).json()
    assert mastery_after == mastery_before

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-cancel-guardian-a@example.com")
    entry = _assignment_entry(
        client, learner_id=learner_id, assignment_id=assignment["assignment_id"]
    )
    assert entry["cancelled_at"] is not None
    assert entry["status"] == "completed"


def test_cancelled_not_started_assignment_stays_visible_and_blocks_start(client, roster):
    learner_id = _register_and_join(
        client, roster, guardian_email="assign-cancel-guardian-b@example.com", learner_name="B"
    )
    roster_id, _join_code = roster

    _login_instructor(client)
    assignment = create_assignment(
        client, roster_id=roster_id, topic_ids=[ENTRY_TOPIC], learner_ids=[learner_id]
    )
    cancel = client.delete(f"/api/rosters/{roster_id}/assignments/{assignment['assignment_id']}")
    assert cancel.status_code == 204, cancel.text

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-cancel-guardian-b@example.com")
    entry = _assignment_entry(
        client, learner_id=learner_id, assignment_id=assignment["assignment_id"]
    )
    assert entry["cancelled_at"] is not None
    assert entry["status"] == "not_started"

    start = client.post(
        f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
    )
    assert start.status_code == 409, start.text
    assert start.json() == {"detail": "assignment_cancelled"}


def test_in_progress_attempt_still_completes_after_cancellation(client, roster):
    learner_id = _register_and_join(
        client, roster, guardian_email="assign-cancel-guardian-c@example.com", learner_name="C"
    )
    roster_id, _join_code = roster

    _login_instructor(client)
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        question_count=1,
        learner_ids=[learner_id],
    )

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-cancel-guardian-c@example.com")
    with patch_generation():
        start = client.post(
            f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
        )
    assert start.status_code == 201, start.text
    quiz_session_id = start.json()["quiz_session_id"]
    question_id = start.json()["question"]["question_id"]

    client.post("/api/auth/logout")
    _login_instructor(client)
    cancel = client.delete(f"/api/rosters/{roster_id}/assignments/{assignment['assignment_id']}")
    assert cancel.status_code == 204, cancel.text

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-cancel-guardian-c@example.com")
    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["status"] == "completed"
    assert summary.json()["score"] == {"correct": 1, "total": 1}

    entry = _assignment_entry(
        client, learner_id=learner_id, assignment_id=assignment["assignment_id"]
    )
    assert entry["cancelled_at"] is not None
    assert entry["status"] == "completed"
