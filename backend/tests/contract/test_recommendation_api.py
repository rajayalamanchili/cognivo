"""Contract test: `GET /api/learners/{learner_id}/recommendations`
matches contracts/api.md (T015).

No LLM call is involved in this endpoint (research.md §1), so unlike
the question-generation contract tests, nothing needs mocking here.
"""

import pytest
from fastapi.testclient import TestClient

from tests.integration.recommendation.scenarios import (
    make_in_progress_topic,
    make_weak_topic,
)


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


def test_full_response_shape_matches_contract(client, db_session, demo_learner, algebra_subject):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.2,
    )
    make_in_progress_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="variables-and-expressions",
        p_mastery=0.5,
    )

    response = client.get(
        f"/api/learners/{learner_id}/recommendations", params={"subject_id": subject_id}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["subject_id"] == subject_id
    assert body["data_sufficiency"] == "confident"
    assert isinstance(body["broad_review_needed"], bool)

    assert len(body["weak_areas"]) == 1
    flag = body["weak_areas"][0]
    assert flag["topic_id"] == "order-of-operations"
    assert flag["display_name"]
    assert flag["p_mastery"] == pytest.approx(0.2)
    assert len(flag["evidence"]) == 3
    for citation in flag["evidence"]:
        assert citation["event_id"]
        assert citation["question_id"]
        assert citation["question_stem"]
        assert "answer_correct" in citation
        assert "posterior_p_mastery" in citation
        assert citation["created_at"]

    next_step = flag["next_step"]
    assert next_step["recommended_topic_id"]
    assert next_step["reason"] in (
        "direct_practice",
        "prerequisite_gap",
        "prerequisite_not_yet_assessed",
    )
    assert isinstance(next_step["prerequisite_chain"], list)

    assert body["in_progress_topic_ids"] == ["variables-and-expressions"]
    assert "integers-and-operations" in body["not_yet_assessed_topic_ids"]
    assert body["insufficient_data_topic_ids"] == []


def test_unknown_subject_returns_404(client, db_session, demo_learner):
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/recommendations",
        params={"subject_id": "not-a-real-subject"},
    )
    assert response.status_code == 404


def test_new_learner_with_no_history_returns_200_not_an_error(
    client, db_session, demo_learner, algebra_subject
):
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/recommendations",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_sufficiency"] == "insufficient_data"
    assert body["weak_areas"] == []
    assert body["broad_review_needed"] is False
