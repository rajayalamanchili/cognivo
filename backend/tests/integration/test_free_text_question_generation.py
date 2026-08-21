"""Integration test: `GET /api/learners/{id}/next-question` for a
free-text-configured topic carries a rubric before display (spec 007
FR-001, FR-002, SC-001), T013.
"""

from src.models.generated_question import GeneratedQuestion
from tests.integration.free_text_helpers import (
    FREE_TEXT_TOPIC_ID,
    make_free_text_topic_next_up,
    patch_free_text_generation,
)


def test_next_question_is_free_text_with_persisted_rubric(
    db_session, demo_learner, algebra_subject
):
    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    make_free_text_topic_next_up(db_session, demo_learner.learner_id, algebra_subject.subject_id)

    with patch_free_text_generation():
        response = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["topic_id"] == FREE_TEXT_TOPIC_ID
    assert body["question_type"] == "free_text"
    assert body["options"] is None

    question = db_session.get(GeneratedQuestion, body["question_id"])
    assert question is not None
    criteria = question.answer_key["criteria"]
    assert len(criteria) >= 1
    for criterion in criteria:
        assert criterion["description"]
        assert criterion["weight"] > 0
