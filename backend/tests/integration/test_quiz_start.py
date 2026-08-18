"""Integration test: `POST /api/quizzes` (contracts/api.md), T011.

First question always at `easy` difficulty for `topic_ids[0]`, `422` on
empty/duplicate `topic_ids` or `question_count` outside 1-50 (FR-001),
`404` on unknown/unvalidated/cross-subject `topic_ids`.
"""

from fastapi.testclient import TestClient

from tests.integration.quiz_helpers import patch_generation

_ENTRY_TOPIC = "integers-and-operations"


def test_starts_a_quiz_with_first_question_at_easy(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    with patch_generation():
        response = client.post(
            "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 3}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["question"]["topic_id"] == _ENTRY_TOPIC
    assert body["question"]["difficulty"] == "easy"
    assert body["question"]["question_type"] == "multiple_choice"


def test_422_on_empty_topic_ids(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.post("/api/quizzes", json={"topic_ids": [], "question_count": 3})
    assert response.status_code == 422, response.text


def test_422_on_duplicate_topic_ids(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.post(
        "/api/quizzes",
        json={"topic_ids": [_ENTRY_TOPIC, _ENTRY_TOPIC], "question_count": 3},
    )
    assert response.status_code == 422, response.text


def test_422_on_question_count_below_one(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.post(
        "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 0}
    )
    assert response.status_code == 422, response.text


def test_422_on_question_count_above_fifty(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.post(
        "/api/quizzes", json={"topic_ids": [_ENTRY_TOPIC], "question_count": 51}
    )
    assert response.status_code == 422, response.text


def test_404_on_unknown_topic_id(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    response = client.post(
        "/api/quizzes", json={"topic_ids": ["not-a-real-topic"], "question_count": 3}
    )
    assert response.status_code == 404, response.text


def test_404_when_topics_span_more_than_one_subject(
    db_session, demo_learner, algebra_subject, biology_subject
):
    from src.api.main import app

    algebra_topic = _ENTRY_TOPIC
    biology_topic = next(t.topic_id for t in biology_subject.topics if t.is_entry_level)

    client = TestClient(app)
    response = client.post(
        "/api/quizzes",
        json={"topic_ids": [algebra_topic, biology_topic], "question_count": 3},
    )
    assert response.status_code == 404, response.text
