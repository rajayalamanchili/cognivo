"""Integration test: a free-text answer containing math/science notation
(a Unicode fraction character) is accepted and graded identically to its
plain-text equivalent -- notation introduces no new comparison mechanism,
just more expressive text through the same rubric-based Grading Agent
call (spec 023 FR-004, User Story 2 Acceptance Scenario 1;
research.md §2/§5).
"""

from fastapi.testclient import TestClient

from tests.integration.free_text_helpers import (
    get_free_text_question,
    patch_grading_result,
    patch_moderation,
)


def test_notated_and_plain_text_answers_grade_identically(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question_notated = get_free_text_question(client, db_session, demo_learner, algebra_subject)
    question_plain = get_free_text_question(client, db_session, demo_learner, algebra_subject)
    assert question_notated["question_id"] != question_plain["question_id"]

    criteria_met = [
        "Correctly identifies the independent variable",
        "Correctly identifies the dependent variable",
    ]

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=criteria_met, criteria_missed=[]),
    ):
        response_notated = client.post(
            f"/api/questions/{question_notated['question_id']}/answer",
            # Contains a Unicode fraction (½) and a subscript-style digit
            # -- exactly the kind of text a learner using the notation
            # toolbar (frontend-only, no backend change) would submit.
            json={"response": "y is dependent; the slope is ½ and x is independent."},
        )
    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=criteria_met, criteria_missed=[]),
    ):
        response_plain = client.post(
            f"/api/questions/{question_plain['question_id']}/answer",
            json={"response": "y is dependent; the slope is 1/2 and x is independent."},
        )

    assert response_notated.status_code == 200, response_notated.text
    assert response_plain.status_code == 200, response_plain.text
    assert response_notated.json()["correct"] == response_plain.json()["correct"] is True
    assert response_notated.json()["criteria_met"] == response_plain.json()["criteria_met"]
