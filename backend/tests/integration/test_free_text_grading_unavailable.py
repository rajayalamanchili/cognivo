"""Integration test: the Grading Agent unreachable/timing out triggers a
bounded retry, then surfaces `503 grading_unavailable`; no
`ANSWER_SUBMITTED` event is written and `question_id` remains answerable
once the Grading Agent is reachable again (spec 007 FR-010), T020.
"""

from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.services.grading_client.client import MAX_ATTEMPTS
from tests.integration.free_text_helpers import get_free_text_question, patch_moderation


def test_unreachable_grading_agent_retries_then_returns_503(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    unreachable = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    with (
        patch_moderation(allowed=True),
        patch("src.services.grading_client.client._call_grading_agent_once", new=unreachable),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "a normal, on-topic answer"},
        )

    assert response.status_code == 503, response.text
    assert response.json() == {"error": "grading_unavailable"}
    assert unreachable.await_count == MAX_ATTEMPTS  # bounded retry, not unlimited

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .all()
    )
    assert len(events) == 0

    # question_id remains answerable once the Grading Agent is reachable.
    from tests.integration.free_text_helpers import patch_grading_result

    with (
        patch_moderation(allowed=True),
        patch_grading_result(graduated_score=1.0, criteria_met=["a"], criteria_missed=[]),
    ):
        retry = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "a normal, on-topic answer"},
        )
    assert retry.status_code == 200, retry.text
