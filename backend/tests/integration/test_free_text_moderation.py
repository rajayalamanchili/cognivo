"""Integration test: a moderation-flagged submission returns `422
moderation_rejected`, writes a `free_text_submission_rejected` event
with `reason: "moderation"`, produces no `ANSWER_SUBMITTED` event, and
`question_id` remains answerable (spec 007 FR-012, SC-007), T018.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.free_text_helpers import (
    get_free_text_question,
    patch_grading_result,
    patch_moderation,
)


def test_moderation_rejected_submission_is_logged_and_leaves_question_answerable(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    with patch_moderation(allowed=False), patch_grading_result(graduated_score=1.0) as grading_mock:
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "some abusive content"},
        )
        assert response.status_code == 422, response.text
        assert response.json() == {"error": "moderation_rejected"}
        grading_mock.assert_not_called()

    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.question_id == question["question_id"])
        .all()
    )
    rejected = [
        e for e in events if e.event_type == AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED
    ]
    submitted = [e for e in events if e.event_type == AssessmentEventType.ANSWER_SUBMITTED]
    assert len(rejected) == 1
    assert rejected[0].payload["reason"] == "moderation"
    assert len(submitted) == 0

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=["a"], criteria_missed=[]),
    ):
        retry = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "a revised, on-topic answer"},
        )
    assert retry.status_code == 200, retry.text
