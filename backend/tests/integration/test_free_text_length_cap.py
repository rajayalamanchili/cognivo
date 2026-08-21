"""Integration test: an over-length free-text submission returns `422
answer_too_long` before any moderation or grading call is made, and
`question_id` remains answerable afterward (spec 007 FR-015, SC-009),
T016.
"""

from fastapi.testclient import TestClient

from src.services.grading_client.guardrails import MAX_ANSWER_LENGTH
from tests.integration.free_text_helpers import (
    get_free_text_question,
    patch_grading_result,
    patch_moderation,
)


def test_over_length_answer_is_rejected_before_moderation_or_grading(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)
    too_long_text = "x" * (MAX_ANSWER_LENGTH + 1)

    with (
        patch_moderation(allowed=True) as moderation_mock,
        patch_grading_result(graduated_score=1.0) as grading_mock,
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": too_long_text},
        )

        assert response.status_code == 422, response.text
        assert response.json() == {"error": "answer_too_long", "max_length": MAX_ANSWER_LENGTH}
        moderation_mock.assert_not_called()
        grading_mock.assert_not_called()

    # question_id remains answerable: a within-limit resubmission succeeds.
    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=["a"], criteria_missed=[]),
    ):
        retry = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "a short, valid answer"},
        )
    assert retry.status_code == 200, retry.text
