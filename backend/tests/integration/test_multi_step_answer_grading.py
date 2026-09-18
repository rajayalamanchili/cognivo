"""Integration test: a stepwise submission is graded step by step,
returning the first step that diverges instead of one undifferentiated
"incorrect" -- and an all-correct submission behaves exactly like any
other correct answer today (spec 018 FR-004, FR-006, FR-007, Acceptance
Scenario 2/3, SC-001, SC-002), T012. Mirrors
`test_free_text_answer_grading.py`.
"""

from fastapi.testclient import TestClient

from tests.integration.multi_step_helpers import (
    all_correct_agent_response,
    diverges_at_step_response,
    get_multi_step_question,
    patch_grading_agent_call,
    patch_moderation,
)


def test_all_correct_submission_is_correct_and_updates_mastery(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(response_text=all_correct_agent_response()),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={
                "response": [
                    "Subtract 2 from both sides: 3x = 12",
                    "Divide both sides by 3: x = 4",
                ]
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["correct"] is True
    assert body["first_diverging_step_index"] is None
    assert len(body["step_results"]) == 2
    assert all(step["correct"] for step in body["step_results"])
    assert body["posterior_p_mastery"] > (body["prior_p_mastery"] or 0)


def test_wrong_at_step_1_names_that_step_and_omits_later_steps(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(response_text=diverges_at_step_response(1)),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={
                "response": [
                    "Subtract 2 from both sides: 3x = 12",
                    "Divide both sides by 3: x = 5",
                ]
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["correct"] is False
    assert body["first_diverging_step_index"] == 1
    # FR-006: exactly 2 entries (step 0 and the diverging step 1), never
    # more -- no step after the divergence is reported.
    assert len(body["step_results"]) == 2
    assert body["step_results"][0]["correct"] is True
    assert body["step_results"][1]["correct"] is False
    assert body["posterior_p_mastery"] < (body["prior_p_mastery"] or 1.0)


def test_identical_submissions_to_identical_rubrics_produce_byte_identical_step_results(
    db_session, demo_learner, algebra_subject
):
    """SC-002: two learners (here, two disposable questions for the same
    learner) submitting byte-identical stepwise answers to the same
    rubric always receive byte-identical step-level results."""
    from src.api.main import app

    client = TestClient(app)
    responses = []
    for _ in range(2):
        question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)
        with (
            patch_moderation(allowed=True),
            patch_grading_agent_call(response_text=diverges_at_step_response(1)),
        ):
            response = client.post(
                f"/api/questions/{question['question_id']}/answer",
                json={
                    "response": [
                        "Subtract 2 from both sides: 3x = 12",
                        "Divide both sides by 3: x = 5",
                    ]
                },
            )
        assert response.status_code == 200, response.text
        responses.append(response.json())

    assert responses[0]["step_results"] == responses[1]["step_results"]
    assert responses[0]["first_diverging_step_index"] == responses[1]["first_diverging_step_index"]
    assert responses[0]["graduated_score"] == responses[1]["graduated_score"]
