"""Integration test: an assigned quiz's difficulty-adaptation and
grading/mastery-update behavior is identical to a non-assigned quiz
given the same scripted answer sequence (research.md §1, SC-002's hard
gate, T021).

Both paths call the exact same `start_quiz()`/`generate_quiz_question()`/
`record_quiz_answer()` mechanism (spec 005/006, unmodified) -- this test
is the structural guarantee's actual proof: two independent learners,
starting from the same fresh BKT prior, driven through an identical
correct/incorrect sequence, must land on identical per-question
difficulty and identical final `p_mastery`/`band`.

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

_CORRECT_SEQUENCE = [True, True, False, True]


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _drive_quiz(client, *, start_response, correct_sequence):
    """Answers each question in `correct_sequence` in order, fetching the
    next one via `GET .../next-question` between answers -- exactly
    spec 005's own quickstart pattern. Returns the difficulty shown for
    each question, in order."""
    difficulties = [start_response["question"]["difficulty"]]
    question_id = start_response["question"]["question_id"]
    quiz_session_id = start_response["quiz_session_id"]

    for index, correct in enumerate(correct_sequence):
        answer = client.post(
            f"/api/questions/{question_id}/answer", json={"response": 0 if correct else 1}
        )
        assert answer.status_code == 200, answer.text

        if index == len(correct_sequence) - 1:
            break
        with patch_generation():
            next_question = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
        assert next_question.status_code == 200, next_question.text
        difficulties.append(next_question.json()["question"]["difficulty"])
        question_id = next_question.json()["question"]["question_id"]

    return difficulties


def _mastery_entry(client, *, learner_id, subject_id, topic_id):
    response = client.get(
        f"/api/learners/{learner_id}/mastery-state?subject_id={subject_id}"
    )
    assert response.status_code == 200, response.text
    return next(t for t in response.json()["topics"] if t["topic_id"] == topic_id)


def test_assigned_quiz_matches_non_assigned_quiz_difficulty_and_mastery(
    client, demo_learner, algebra_subject
):
    with patch_generation():
        plain_start = client.post(
            "/api/quizzes", json={"topic_ids": [ENTRY_TOPIC], "question_count": 4}
        )
    assert plain_start.status_code == 200, plain_start.text
    plain_difficulties = _drive_quiz(
        client, start_response=plain_start.json(), correct_sequence=_CORRECT_SEQUENCE
    )
    plain_mastery = _mastery_entry(
        client,
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=ENTRY_TOPIC,
    )

    register_instructor(client, "assign-parity-instructor@example.com")
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)

    client.post("/api/auth/logout")
    _guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email="assign-parity-guardian@example.com", learner_name="Learner"
    )
    join_roster(client, learner_id=learner_id, join_code=join_code)

    client.post("/api/auth/logout")
    login_instructor(client, "assign-parity-instructor@example.com")
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        question_count=4,
        learner_ids=[learner_id],
    )

    client.post("/api/auth/logout")
    login = client.post(
        "/api/auth/guardian/login",
        json={"email": "assign-parity-guardian@example.com", "password": "correct horse"},
    )
    assert login.status_code == 200, login.text

    with patch_generation():
        assigned_start = client.post(
            f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
        )
    assert assigned_start.status_code == 201, assigned_start.text
    assigned_difficulties = _drive_quiz(
        client, start_response=assigned_start.json(), correct_sequence=_CORRECT_SEQUENCE
    )
    assigned_mastery = _mastery_entry(
        client, learner_id=learner_id, subject_id=algebra_subject.subject_id, topic_id=ENTRY_TOPIC
    )

    assert assigned_difficulties == plain_difficulties
    assert assigned_mastery["p_mastery"] == plain_mastery["p_mastery"]
    assert assigned_mastery["band"] == plain_mastery["band"]
    assert assigned_mastery["status"] == plain_mastery["status"] == "scored"
