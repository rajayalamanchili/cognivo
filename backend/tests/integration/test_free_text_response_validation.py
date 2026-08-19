"""Integration test: a Grading Agent response that fails rubric-shape
validation (wrong criteria count/order, out-of-range score) is rejected
and retried, falling back to `503 grading_unavailable` once retries are
exhausted (spec 007 FR-014), T021.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.services.grading_client.client import MAX_ATTEMPTS
from tests.integration.free_text_helpers import get_free_text_question, patch_moderation


def _malformed_response() -> str:
    # DEFAULT_RUBRIC_CRITERIA has 2 criteria; this response has only 1 --
    # a criteria-count mismatch (FR-014's validation gate).
    return json.dumps(
        {
            "graduated_score": 1.0,
            "criteria_results": [{"description": "wrong criterion", "met": True}],
            "grading_logic_version": "v1",
        }
    )


def test_malformed_grading_response_is_retried_then_returns_503(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    malformed = AsyncMock(return_value=_malformed_response())
    with (
        patch_moderation(allowed=True),
        patch("src.services.grading_client.client._call_grading_agent_once", new=malformed),
    ):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "a normal, on-topic answer"},
        )

    assert response.status_code == 503, response.text
    assert response.json() == {"error": "grading_unavailable"}
    assert malformed.await_count == MAX_ATTEMPTS
