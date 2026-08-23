"""Integration test: guardian-mediated start/continue authorization for
an assigned quiz (contracts/api.md, T017).

`not_your_learner` (the requesting guardian doesn't own the learner_id
in the URL) and `not_targeted` (the guardian's own learner isn't in this
assignment's target list) are distinct failure modes on start; the two
extended continuation routes (`GET .../next-question`, `POST
.../answer`) each reject a guardian who isn't the assignment-linked
session's own learner's guardian with `not_learner_guardian`. The
positive path (learner A's own guardian starting, continuing, and
answering) proves FR-006/FR-013's guardian-mediated flow actually works
end to end, not just that it rejects the wrong caller.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

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
    """Instructor owns a roster with learner A (guardian A, targeted),
    a second learner of guardian A's own (not targeted), and learner B
    (guardian B, not targeted). Returns a dict of ids; leaves guardian A
    logged in with `learner_a` started (a fresh quiz question already
    generated) so continuation tests don't need to repeat that setup."""
    register_instructor(client, "assign-auth-instructor@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    guardian_a_id, learner_a_id = register_guardian_with_learner(
        client, guardian_email="assign-auth-guardian-a@example.com", learner_name="Learner A"
    )
    join_roster(client, learner_id=learner_a_id, join_code=join_code)
    second = client.post("/api/learners", json={"display_name": "Learner A2"})
    assert second.status_code == 201, second.text
    learner_a2_id = second.json()["learner_id"]
    join_roster(client, learner_id=learner_a2_id, join_code=join_code)

    client.post("/api/auth/logout")
    guardian_b_id, learner_b_id = register_guardian_with_learner(
        client, guardian_email="assign-auth-guardian-b@example.com", learner_name="Learner B"
    )
    join_roster(client, learner_id=learner_b_id, join_code=join_code)

    client.post("/api/auth/logout")
    login_instructor(client, "assign-auth-instructor@example.com")
    assignment = create_assignment(
        client, roster_id=roster_id, topic_ids=[ENTRY_TOPIC], learner_ids=[learner_a_id]
    )

    client.post("/api/auth/logout")
    return {
        "assignment_id": assignment["assignment_id"],
        "guardian_a_id": guardian_a_id,
        "learner_a_id": learner_a_id,
        "learner_a2_id": learner_a2_id,
        "guardian_b_id": guardian_b_id,
        "learner_b_id": learner_b_id,
    }


def _login_guardian(client, email):
    response = client.post(
        "/api/auth/guardian/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def test_403_not_your_learner_on_start(client, scenario):
    _login_guardian(client, "assign-auth-guardian-b@example.com")
    response = client.post(
        f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_a_id']}/start"
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_your_learner"}


def test_403_not_targeted_on_start(client, scenario):
    _login_guardian(client, "assign-auth-guardian-a@example.com")
    response = client.post(
        f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_a2_id']}/start"
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_targeted"}


def test_guardian_starts_continues_and_answers(client, scenario):
    _login_guardian(client, "assign-auth-guardian-a@example.com")
    # A fresh `with patch_generation():` block per API call (no explicit
    # `stems`) -- quiz_helpers.py's own documented convention -- so each
    # generated question gets a distinct UUID-suffixed stem and dedup
    # detection never falsely treats the second question as a repeat of
    # the first (which a shared, explicit stems list would, since each
    # new `with` block restarts that list's cycle at index 0).
    with patch_generation():
        start = client.post(
            f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_a_id']}/start"
        )
    assert start.status_code == 201, start.text
    body = start.json()
    assert body["status"] == "in_progress"
    quiz_session_id = body["quiz_session_id"]
    question_id = body["question"]["question_id"]

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    with patch_generation():
        next_question = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert next_question.status_code == 200, next_question.text
    assert next_question.json()["status"] == "in_progress"


def test_403_not_learner_guardian_on_next_question(client, scenario):
    _login_guardian(client, "assign-auth-guardian-a@example.com")
    with patch_generation(["assigned quiz q1"]):
        start = client.post(
            f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_a_id']}/start"
        )
    quiz_session_id = start.json()["quiz_session_id"]

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-auth-guardian-b@example.com")
    response = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_learner_guardian"}


def test_403_not_learner_guardian_on_answer(client, scenario):
    _login_guardian(client, "assign-auth-guardian-a@example.com")
    with patch_generation(["assigned quiz q1"]):
        start = client.post(
            f"/api/assignments/{scenario['assignment_id']}/learners/{scenario['learner_a_id']}/start"
        )
    question_id = start.json()["question"]["question_id"]

    client.post("/api/auth/logout")
    _login_guardian(client, "assign-auth-guardian-b@example.com")
    response = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_learner_guardian"}


def test_non_assignment_quiz_next_question_unaffected_by_missing_session(
    client, demo_learner, algebra_subject
):
    """No guardian session at all, and the quiz isn't assignment-linked
    -- confirms `assert_guardian_owns_assignment_session` stays a true
    no-op for the pre-existing demo/M5 quiz path (research.md §2's hard
    regression boundary, SC-002)."""
    with patch_generation(["plain quiz q1"]):
        start = client.post(
            "/api/quizzes", json={"topic_ids": [ENTRY_TOPIC], "question_count": 3}
        )
    assert start.status_code == 200, start.text
    quiz_session_id = start.json()["quiz_session_id"]

    with patch_generation(["plain quiz q2"]):
        response = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert response.status_code == 200, response.text
