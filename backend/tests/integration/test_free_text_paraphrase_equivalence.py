"""Integration test: two differently-worded, equally-correct free-text
answers submitted to two instances of the same question (same rubric,
different `question_id`s) receive identical `correct`/`criteria_met`
outcomes -- the backend applies no exact-string-match logic of its own,
only the Grading Agent's rubric-based result (spec 007 FR-004, User
Story 1 Acceptance Scenario 3), T023.
"""

from fastapi.testclient import TestClient

from tests.integration.free_text_helpers import (
    get_free_text_question,
    patch_grading_result,
    patch_moderation,
)


def test_two_paraphrased_correct_answers_grade_identically(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question_a = get_free_text_question(client, db_session, demo_learner, algebra_subject)
    question_b = get_free_text_question(client, db_session, demo_learner, algebra_subject)
    assert question_a["question_id"] != question_b["question_id"]

    criteria_met = [
        "Correctly identifies the independent variable",
        "Correctly identifies the dependent variable",
    ]

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=criteria_met, criteria_missed=[]),
    ):
        response_a = client.post(
            f"/api/questions/{question_a['question_id']}/answer",
            json={"response": "x is independent, y is dependent."},
        )
    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=criteria_met, criteria_missed=[]),
    ):
        response_b = client.post(
            f"/api/questions/{question_b['question_id']}/answer",
            json={
                "response": "The dependent variable here is y, and x plays the independent role."
            },
        )

    assert response_a.status_code == 200, response_a.text
    assert response_b.status_code == 200, response_b.text
    assert response_a.json()["correct"] == response_b.json()["correct"] is True
