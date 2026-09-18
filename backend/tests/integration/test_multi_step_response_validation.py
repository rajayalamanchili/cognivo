"""Integration test: submitting fewer or more steps than the question's
rubric expects is rejected with `422 step_count_mismatch` before any
moderation or grading call is made, and the question remains open for
resubmission (spec 018 FR-012, mirrors `test_free_text_length_cap.py`/
`test_free_text_response_validation.py`'s rejection-path assertions),
T027.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.multi_step_helpers import (
    all_correct_agent_response,
    get_multi_step_question,
    patch_grading_agent_call,
    patch_moderation,
)


def test_fewer_steps_than_expected_is_rejected_before_moderation_or_grading(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True) as moderation_mock,
        patch_grading_agent_call(response_text=all_correct_agent_response()) as grading_mock,
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": ["Subtract 2 from both sides: 3x = 12"]},
        )

        assert response.status_code == 422, response.text
        assert response.json() == {
            "error": "step_count_mismatch",
            "expected_step_count": 2,
            "submitted_step_count": 1,
        }
        moderation_mock.assert_not_called()
        grading_mock.assert_not_called()

    mismatch_events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.STEP_COUNT_MISMATCH_REJECTED,
        )
        .all()
    )
    assert len(mismatch_events) == 1
    assert mismatch_events[0].payload == {"expected_step_count": 2, "submitted_step_count": 1}

    answer_submitted_events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .all()
    )
    assert answer_submitted_events == []

    # question_id remains answerable: a correctly-shaped resubmission succeeds.
    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(response_text=all_correct_agent_response()),
    ):
        retry = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={
                "response": [
                    "Subtract 2 from both sides: 3x = 12",
                    "Divide both sides by 3: x = 4",
                ]
            },
        )
    assert retry.status_code == 200, retry.text


def test_more_steps_than_expected_is_rejected(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True) as moderation_mock,
        patch_grading_agent_call(response_text=all_correct_agent_response()) as grading_mock,
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={
                "response": [
                    "Subtract 2 from both sides: 3x = 12",
                    "Divide both sides by 3: x = 4",
                    "An extra, unexpected step",
                ]
            },
        )

        assert response.status_code == 422, response.text
        assert response.json() == {
            "error": "step_count_mismatch",
            "expected_step_count": 2,
            "submitted_step_count": 3,
        }
        moderation_mock.assert_not_called()
        grading_mock.assert_not_called()

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .all()
    )
    assert events == []
