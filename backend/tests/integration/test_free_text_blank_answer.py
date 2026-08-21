"""Integration test: a blank/whitespace-only free-text answer still
returns a definite `200` (`correct: false`), never a validation error
(spec.md Edge Cases), T015.
"""

from fastapi.testclient import TestClient

from tests.integration.free_text_helpers import (
    get_free_text_question,
    patch_grading_result,
    patch_moderation,
)


def test_blank_answer_returns_200_correct_false(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=0.0, criteria_met=[], criteria_missed=["a", "b"]),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": ""},
        )

    assert response.status_code == 200, response.text
    assert response.json()["correct"] is False


def test_whitespace_only_answer_returns_200_correct_false(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=0.0, criteria_met=[], criteria_missed=["a", "b"]),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "   "},
        )

    assert response.status_code == 200, response.text
    assert response.json()["correct"] is False
