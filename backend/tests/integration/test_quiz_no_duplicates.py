"""Integration test: zero near-duplicates within one quiz session
(SC-004), T027.

Runs a single-topic quiz with `question_count` greater than Milestone
1's 5-question default lookback, confirming no two questions in the
session are near-duplicates -- the dedup lookback is widened to the
quiz's own `question_count` (research.md §3), not capped at 5.
"""

import uuid

from fastapi.testclient import TestClient

from src.models.generated_question import GeneratedQuestion
from src.services.dedup.checker import DEFAULT_LOOKBACK, is_near_duplicate
from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_zero_near_duplicates_across_a_quiz_longer_than_the_default_lookback(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    question_count = DEFAULT_LOOKBACK + 3
    client = TestClient(app)

    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_ENTRY_TOPIC], "question_count": question_count},
        )
    assert start.status_code == 200, start.text
    quiz = start.json()
    question_id = quiz["question"]["question_id"]

    for i in range(question_count):
        answer = client.post(
            f"/api/questions/{question_id}/answer", json={"response": i % 4}
        )
        assert answer.status_code == 200, answer.text

        if i == question_count - 1:
            break

        with patch_generation():
            next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
        assert next_q.status_code == 200, next_q.text
        body = next_q.json()
        assert body["status"] == "in_progress"
        question_id = body["question"]["question_id"]

    stems = [
        row.stem
        for row in db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.quiz_session_id == uuid.UUID(quiz["quiz_session_id"]))
        .order_by(GeneratedQuestion.generated_at)
        .all()
    ]
    assert len(stems) == question_count

    for i, stem in enumerate(stems):
        assert not is_near_duplicate(stem, stems[:i]), f"stem #{i} is a near-duplicate: {stem!r}"
