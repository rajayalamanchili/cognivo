"""Integration test: the recorded `ANSWER_SUBMITTED` event's payload for a
multi-step answer matches data-model.md's shape exactly -- `graduated_score`,
`first_diverging_step_index`, `step_results`, `grading_logic_version` --
so "why was this marked wrong" has a real, traceable answer at the step
level (spec 018 FR-008), T013. Mirrors
`test_free_text_grading_decision_audit.py`.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.multi_step_helpers import (
    diverges_at_step_response,
    get_multi_step_question,
    patch_grading_agent_call,
    patch_moderation,
)


def test_answer_submitted_event_includes_step_level_grading_decision_detail(
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

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .one()
    )
    assert event.payload["graduated_score"] == 0.5
    assert event.payload["first_diverging_step_index"] == 1
    assert event.payload["grading_logic_version"] == "v1"
    step_results = event.payload["step_results"]
    assert len(step_results) == 2
    assert step_results[0] == {
        "step_index": 0,
        "correct": True,
        "criteria_met": ["Chooses to subtract 2 from both sides", "Correctly computes 3x = 12"],
        "criteria_missed": [],
    }
    assert step_results[1] == {
        "step_index": 1,
        "correct": False,
        "criteria_met": ["Chooses to divide both sides by 3"],
        "criteria_missed": ["Correctly computes x = 4"],
    }

    body = response.json()
    assert body["graduated_score"] == 0.5
    assert body["first_diverging_step_index"] == 1
    assert body["step_results"] == step_results
    # The per-step breakdown replaces the flat criteria fields, it does
    # not sit alongside them (contracts/api.md).
    assert body["criteria_met"] is None
    assert body["criteria_missed"] is None
