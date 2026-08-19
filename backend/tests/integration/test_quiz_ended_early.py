"""Integration test: the dedup-exhaustion -> `ended_early` transition
itself (FR-008, analysis finding C1), T013.

Constrains generation to always return the same stem so retries exhaust
for a topic, then confirms: no new `GeneratedQuestion` row is created,
`QuizSession.status` becomes `ended_early` with `completed_at` set, and
`GET /api/quizzes/{id}` still returns a score/summary in the same shape
FR-005 describes for a normal completion.
"""

import uuid

from fastapi.testclient import TestClient

from src.models.enums import QuizSessionStatus
from src.models.generated_question import GeneratedQuestion
from src.models.quiz_session import QuizSession
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_ended_early_when_dedup_retries_exhausted(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation(stems=["identical stem"]):
        start = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 10}
        )
    assert start.status_code == 200, start.text
    quiz = start.json()
    quiz_session_id = quiz["quiz_session_id"]

    initial_count = (
        db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.quiz_session_id == uuid.UUID(quiz_session_id))
        .count()
    )
    assert initial_count == 1

    with patch_generation(stems=["identical stem"]):
        response = client.get(f"/api/quizzes/{quiz_session_id}/next-question")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ended_early"
    assert body["question"] is None

    count_after = (
        db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.quiz_session_id == uuid.UUID(quiz_session_id))
        .count()
    )
    assert count_after == initial_count

    quiz_row = db_session.get(QuizSession, uuid.UUID(quiz_session_id))
    db_session.refresh(quiz_row)
    assert quiz_row.status == QuizSessionStatus.ENDED_EARLY
    assert quiz_row.completed_at is not None

    summary = client.get(f"/api/quizzes/{quiz_session_id}")
    assert summary.status_code == 200, summary.text
    summary_body = summary.json()
    assert summary_body["status"] == "ended_early"
    assert summary_body["score"] == {"correct": 0, "total": 0}
    assert summary_body["summary"] == []
