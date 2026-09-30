"""Integration test: a moderation-flagged submission returns `422
moderation_rejected`, writes a `free_text_submission_rejected` event
with `reason: "moderation"`, produces no `ANSWER_SUBMITTED` event, and
`question_id` remains answerable (spec 007 FR-012, SC-007), T018.

`test_moderation_service_failure_is_never_cached_as_a_block` (spec 026
PR feedback, Principles II/V) covers the caching-era regression: a
transient classifier failure must fail closed exactly like a genuine
block, but must never be persisted to `moderation_cache` as if it were
one -- otherwise one outage permanently blocks that exact text for
every learner until the instruction version changes.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.moderation_cache import ModerationCache
from src.services.grading_client.moderation import ModerationUnavailableError
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


def test_moderation_service_failure_is_never_cached_as_a_block(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)
    submitted_text = "an answer submitted during a transient classifier outage"

    with (
        patch(
            "src.api.routes.questions.check_moderation",
            new=AsyncMock(side_effect=ModerationUnavailableError("no response")),
        ),
        patch_grading_result(graduated_score=1.0) as grading_mock,
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": submitted_text},
        )
        assert response.status_code == 422, response.text
        assert response.json() == {"error": "moderation_rejected"}
        grading_mock.assert_not_called()

    rejected = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED,
        )
        .all()
    )
    assert len(rejected) == 1
    assert rejected[0].payload["reason"] == "moderation_unavailable"
    # The whole point: a service failure must leave zero trace in the
    # cache -- otherwise this exact text is permanently blocked for
    # every learner, not just rejected for this one request.
    assert db_session.query(ModerationCache).count() == 0

    with patch_moderation(allowed=True), patch_grading_result(graduated_score=1.0):
        retry = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": submitted_text},
        )
    assert retry.status_code == 200, retry.text
