"""Integration test: `GET /api/quizzes/{id}/next-question`
(contracts/api.md), T012.

Difficulty escalates/de-escalates per the streak rule end to end
against a real DB; `409` once the quiz is `completed`/`ended_early`.
"""

from fastapi.testclient import TestClient

from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def _start_quiz(client: TestClient, *, topic_ids, question_count):
    with patch_generation():
        response = client.post(
            "/api/quizzes", json={"topic_ids": topic_ids, "question_count": question_count}
        )
    assert response.status_code == 200, response.text
    return response.json()


def _answer(client: TestClient, question_id: str, *, correct: bool):
    response = client.post(
        f"/api/questions/{question_id}/answer", json={"response": 0 if correct else 1}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _next_question(client: TestClient, quiz_session_id: str):
    with patch_generation():
        response = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    return response


def test_difficulty_escalates_after_two_consecutive_correct_answers(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    quiz = _start_quiz(client, topic_ids=[_ENTRY_TOPIC], question_count=6)
    assert quiz["question"]["difficulty"] == "easy"

    _answer(client, quiz["question"]["question_id"], correct=True)
    second = _next_question(client, quiz["quiz_session_id"])
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert second_body["question"]["difficulty"] == "easy"  # only 1 correct so far

    _answer(client, second_body["question"]["question_id"], correct=True)
    third = _next_question(client, quiz["quiz_session_id"])
    assert third.json()["question"]["difficulty"] == "medium"


def test_difficulty_deescalates_after_two_consecutive_incorrect_answers(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    quiz = _start_quiz(client, topic_ids=[_ENTRY_TOPIC], question_count=6)

    # Get to medium first via two correct answers.
    _answer(client, quiz["question"]["question_id"], correct=True)
    q2 = _next_question(client, quiz["quiz_session_id"]).json()
    _answer(client, q2["question"]["question_id"], correct=True)
    q3 = _next_question(client, quiz["quiz_session_id"]).json()
    assert q3["question"]["difficulty"] == "medium"

    _answer(client, q3["question"]["question_id"], correct=False)
    q4 = _next_question(client, quiz["quiz_session_id"]).json()
    assert q4["question"]["difficulty"] == "medium"  # only 1 incorrect so far

    _answer(client, q4["question"]["question_id"], correct=False)
    q5 = _next_question(client, quiz["quiz_session_id"]).json()
    assert q5["question"]["difficulty"] == "easy"


def test_404_for_unknown_quiz_session_id(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/quizzes/00000000-0000-0000-0000-000000000000/next-question")
    assert response.status_code == 404


def test_409_once_quiz_is_completed(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    quiz = _start_quiz(client, topic_ids=[_ENTRY_TOPIC], question_count=1)
    _answer(client, quiz["question"]["question_id"], correct=True)

    response = _next_question(client, quiz["quiz_session_id"])
    assert response.status_code == 409, response.text
