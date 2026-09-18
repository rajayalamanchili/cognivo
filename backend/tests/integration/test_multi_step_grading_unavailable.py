"""Integration test: the Grading Agent returning a malformed multi-step
response on every attempt results in `503 grading_unavailable`, no
`ANSWER_SUBMITTED` event written (spec 018, mirrors spec 007's
`test_free_text_grading_unavailable.py`/`test_free_text_response_
validation.py`), T014.
"""

import httpx
from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.services.grading_client.client import MAX_ATTEMPTS
from tests.integration.multi_step_helpers import (
    get_multi_step_question,
    patch_grading_agent_call,
    patch_moderation,
)


def test_unreachable_grading_agent_retries_then_returns_503(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(side_effect=httpx.ConnectError("connection refused")) as mock,
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": ["3x = 12", "x = 4"]},
        )

    assert response.status_code == 503, response.text
    assert response.json() == {"error": "grading_unavailable"}
    assert mock.await_count == MAX_ATTEMPTS  # bounded retry, not unlimited

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .all()
    )
    assert events == []


def test_malformed_response_every_attempt_returns_503(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    # Missing step_results entirely -- fails the validation gate on every
    # one of MAX_ATTEMPTS attempts.
    malformed = (
        '{"graduated_score": 1.0, "first_diverging_step_index": null, '
        '"grading_logic_version": "v1"}'
    )

    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(response_text=malformed),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": ["3x = 12", "x = 4"]},
        )

    assert response.status_code == 503, response.text
    assert response.json() == {"error": "grading_unavailable"}

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question["question_id"],
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .all()
    )
    assert events == []
