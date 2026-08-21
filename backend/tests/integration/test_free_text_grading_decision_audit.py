"""Integration test: the recorded `ANSWER_SUBMITTED` event's payload for a
free-text answer includes `graduated_score`, `criteria_met`,
`criteria_missed`, and `grading_logic_version` -- so "why was this marked
wrong" has a real, traceable answer (spec 007 FR-007, SC-004), T035.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.free_text_helpers import (
    get_free_text_question,
    patch_grading_result,
    patch_moderation,
)


def test_answer_submitted_event_includes_grading_decision_detail(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True),
        patch_grading_result(
            graduated_score=0.82,
            criteria_met=["Correctly identifies the independent variable"],
            criteria_missed=["Correctly identifies the dependent variable"],
            grading_logic_version="v1",
        ),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "The independent variable is x."},
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
    assert event.payload["graduated_score"] == 0.82
    assert event.payload["criteria_met"] == ["Correctly identifies the independent variable"]
    assert event.payload["criteria_missed"] == ["Correctly identifies the dependent variable"]
    assert event.payload["grading_logic_version"] == "v1"

    body = response.json()
    assert body["graduated_score"] == 0.82
    assert body["criteria_met"] == ["Correctly identifies the independent variable"]
    assert body["criteria_missed"] == ["Correctly identifies the dependent variable"]
    assert body["grading_logic_version"] == "v1"
