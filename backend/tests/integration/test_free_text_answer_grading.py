"""Integration test: an on-topic, all-criteria-met free-text answer is
graded `correct: true` and updates `MasteryState` via the same read path
MC/numeric already use (spec 007 FR-004, FR-005, FR-006, SC-002), T014.
"""

from fastapi.testclient import TestClient

from tests.integration.free_text_helpers import (
    get_free_text_question,
    patch_grading_result,
    patch_moderation,
)


def test_all_criteria_met_answer_is_correct_and_updates_mastery(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True),
        patch_grading_result(
            graduated_score=1.0,
            criteria_met=[
                "Correctly identifies the independent variable",
                "Correctly identifies the dependent variable",
            ],
            criteria_missed=[],
        ),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "The independent variable is x, the dependent variable is y."},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["correct"] is True
    assert body["posterior_p_mastery"] != body["prior_p_mastery"]
    assert body["posterior_p_mastery"] > (body["prior_p_mastery"] or 0)
