"""Integration test: a full-path `POST /answer` call for a multi-step
submission, including the retry path, completes within the locked
15-second budget (spec 018 SC-006), T037. Mirrors
`test_free_text_grading_latency.py`'s measurement approach.
"""

import time

from fastapi.testclient import TestClient

from tests.integration.multi_step_helpers import (
    all_correct_agent_response,
    get_multi_step_question,
    patch_grading_agent_call,
    patch_moderation,
)


def test_grading_round_trip_with_one_retry_completes_within_budget(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    # First attempt fails (forcing the retry path), second succeeds.
    with (
        patch_moderation(allowed=True),
        patch_grading_agent_call(
            side_effect=[ConnectionError("transient"), all_correct_agent_response()]
        ) as mock,
    ):
        started = time.monotonic()
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={
                "response": [
                    "Subtract 2 from both sides: 3x = 12",
                    "Divide both sides by 3: x = 4",
                ]
            },
        )
        elapsed = time.monotonic() - started

    assert response.status_code == 200, response.text
    assert mock.await_count == 2
    assert elapsed < 15.0
