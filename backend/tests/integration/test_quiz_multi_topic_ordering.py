"""Integration test: multi-topic round-robin ordering (Edge Cases,
research.md §2), T028.

A 2-topic, 4-question quiz's questions alternate topics in the order
the topics were selected, one question per topic per cycle -- not
completing one topic before starting the next.
"""

from fastapi.testclient import TestClient

from tests.integration.quiz_helpers import patch_generation

_TOPIC_A = "integers-and-operations"
_TOPIC_B = "variables-and-expressions"


def test_questions_alternate_topics_in_selection_order(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        start = client.post(
            "/api/quizzes",
            json={"topic_ids": [_TOPIC_A, _TOPIC_B], "question_count": 4},
        )
    assert start.status_code == 200, start.text
    quiz = start.json()

    topic_sequence = [quiz["question"]["topic_id"]]
    question_id = quiz["question"]["question_id"]

    for _i in range(3):
        answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
        assert answer.status_code == 200, answer.text

        with patch_generation():
            next_q = client.get(f"/api/quizzes/{quiz['quiz_session_id']}/next-question")
        assert next_q.status_code == 200, next_q.text
        body = next_q.json()
        topic_sequence.append(body["question"]["topic_id"])
        question_id = body["question"]["question_id"]

    assert topic_sequence == [_TOPIC_A, _TOPIC_B, _TOPIC_A, _TOPIC_B]
