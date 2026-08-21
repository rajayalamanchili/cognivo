"""Integration test: a free-text grading round trip, including the
retry path, completes within the locked 10-second budget (spec 007
SC-006), T025.
"""

import time
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from tests.integration.free_text_helpers import get_free_text_question, patch_moderation

_GRADING_SUCCESS_TEXT = (
    '{"graduated_score": 1.0, "criteria_results": '
    '[{"description": "Correctly identifies the independent variable", "met": true}, '
    '{"description": "Correctly identifies the dependent variable", "met": true}], '
    '"grading_logic_version": "v1"}'
)


def test_grading_round_trip_with_one_retry_completes_within_budget(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)

    # First attempt fails (forcing the retry path), second succeeds.
    flaky = AsyncMock(side_effect=[ConnectionError("transient"), _GRADING_SUCCESS_TEXT])

    with (
        patch_moderation(allowed=True),
        patch("src.services.grading_client.client._call_grading_agent_once", new=flaky),
    ):
        started = time.monotonic()
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": "x is independent, y is dependent."},
        )
        elapsed = time.monotonic() - started

    assert response.status_code == 200, response.text
    assert flaky.await_count == 2
    assert elapsed < 10.0
