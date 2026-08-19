"""Integration test: `GET /api/quizzes/{id}` (contracts/api.md), T015.

Score/summary shape grouped by (topic, difficulty), correct even while
`in_progress` (partial tally, not an error).
"""

from fastapi.testclient import TestClient

from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_partial_summary_while_in_progress(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 3}
        )
    quiz = start.json()

    client.post(f"/api/questions/{quiz['question']['question_id']}/answer", json={"response": 0})

    summary = client.get(f"/api/quizzes/{quiz['quiz_session_id']}")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["status"] == "in_progress"
    assert body["score"] == {"correct": 1, "total": 1}
    assert body["summary"] == [
        {"topic_id": _ENTRY_TOPIC, "difficulty": "easy", "correct": 1, "total": 1}
    ]


def test_full_summary_on_completion(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 2}
        )
    quiz = start.json()

    client.post(
        f"/api/questions/{quiz['question']['question_id']}/answer", json={"response": 1}
    )
    with patch_generation():
        next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
    assert next_q.status_code == 200, next_q.text
    client.post(
        f"/api/questions/{next_q.json()['question']['question_id']}/answer",
        json={"response": 0},
    )

    summary = client.get(f"/api/quizzes/{quiz['quiz_session_id']}")
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["status"] == "completed"
    assert body["score"] == {"correct": 1, "total": 2}
    assert body["completed_at"] is not None


def test_404_for_unknown_quiz_session_id(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/api/quizzes/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
