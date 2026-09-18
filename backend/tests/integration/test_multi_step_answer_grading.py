"""Integration test: a stepwise submission is graded step by step,
returning the first step that diverges instead of one undifferentiated
"incorrect" -- and an all-correct submission behaves exactly like any
other correct answer today (spec 018 FR-004, FR-006, FR-007, Acceptance
Scenario 2/3, SC-001, SC-002), T012. Mirrors
`test_free_text_answer_grading.py`.
"""

from fastapi.testclient import TestClient

from tests.integration.multi_step_helpers import (
    DEFAULT_STEPS,
    all_correct_agent_response,
    diverges_at_step_response,
    get_multi_step_question,
    patch_grading_agent_call,
    patch_moderation,
    stepwise_agent_response_json,
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


def test_diverging_step_names_the_specific_missed_criterion(
    db_session, demo_learner, algebra_subject
):
    """US2 Acceptance Scenario 1: the diverging step's `criteria_missed`
    names the specific failed criterion, and each step's criteria_met/
    criteria_missed reflect only that step's own rubric -- not aggregated
    across steps (T024)."""
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
    step0, step1 = response.json()["step_results"]
    assert step0["criteria_met"] == [
        "Chooses to subtract 2 from both sides",
        "Correctly computes 3x = 12",
    ]
    assert step0["criteria_missed"] == []
    assert step1["criteria_met"] == ["Chooses to divide both sides by 3"]
    assert step1["criteria_missed"] == ["Correctly computes x = 4"]


def test_wrong_method_is_distinguishable_from_correct_method_wrong_execution(
    db_session, demo_learner, algebra_subject
):
    """FR-005: a computational slip on an otherwise-correct method must be
    distinguishable from choosing the wrong method entirely -- the diverging
    step's `criteria_missed` differs in which criterion it names."""
    from src.api.main import app

    client = TestClient(app)

    question_a = get_multi_step_question(client, db_session, demo_learner, algebra_subject)
    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(response_text=diverges_at_step_response(1)),
    ):
        response_a = client.post(
            f"/api/questions/{question_a['question_id']}/answer",
            json={
                "response": [
                    "Subtract 2 from both sides: 3x = 12",
                    "Divide both sides by 3: x = 5",
                ]
            },
        )
    assert response_a.status_code == 200, response_a.text
    step1_a = response_a.json()["step_results"][1]

    wrong_method_response = stepwise_agent_response_json(
        graduated_score=0.5,
        first_diverging_step_index=1,
        step_results=[
            {
                "step_index": 0,
                "criteria_results": [
                    {"description": c["description"], "met": True}
                    for c in DEFAULT_STEPS[0]["criteria"]
                ],
            },
            {
                "step_index": 1,
                "criteria_results": [
                    {"description": "Chooses to divide both sides by 3", "met": False},
                    {"description": "Correctly computes x = 4", "met": False},
                ],
            },
        ],
    )
    question_b = get_multi_step_question(client, db_session, demo_learner, algebra_subject)
    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(response_text=wrong_method_response),
    ):
        response_b = client.post(
            f"/api/questions/{question_b['question_id']}/answer",
            json={
                "response": [
                    "Subtract 2 from both sides: 3x = 12",
                    "Multiply both sides by 3: x = 36",
                ]
            },
        )
    assert response_b.status_code == 200, response_b.text
    step1_b = response_b.json()["step_results"][1]

    # Case A (correct method, wrong execution): the method criterion is met.
    assert step1_a["criteria_met"] == ["Chooses to divide both sides by 3"]
    assert step1_a["criteria_missed"] == ["Correctly computes x = 4"]
    # Case B (wrong method entirely): the method criterion itself is missed.
    assert step1_b["criteria_met"] == []
    assert step1_b["criteria_missed"] == [
        "Chooses to divide both sides by 3",
        "Correctly computes x = 4",
    ]
