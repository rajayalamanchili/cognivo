"""Integration test: submissions past the per-learner rate limit return
`429 rate_limited`; the limit is proven DB-derived (not in-memory) by
reloading the guardrails module between requests -- simulating a fresh
Vercel Function invocation, matching quickstart.md scenario 9 -- rather
than merely reusing one Python process's module state, which would not
catch a naive in-memory counter (spec 007 FR-016, SC-010, research.md
§6), T017.
"""

import importlib

from fastapi.testclient import TestClient

from src.services.grading_client import guardrails as guardrails_module
from src.services.grading_client.guardrails import (
    MAX_ANSWER_LENGTH,
    RATE_LIMIT_MAX_SUBMISSIONS,
)
from tests.integration.free_text_helpers import get_free_text_question


def test_rate_limit_enforced_after_locked_submission_count(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    question = get_free_text_question(client, db_session, demo_learner, algebra_subject)
    too_long_text = "x" * (MAX_ANSWER_LENGTH + 1)

    for _ in range(RATE_LIMIT_MAX_SUBMISSIONS):
        response = client.post(
            f"/api/questions/{question['question_id']}/answer",
            json={"response": too_long_text},
        )
        assert response.status_code == 422, response.text
        # Reload between requests -- a hypothetical in-memory counter
        # (a module-level dict/global) would reset here; a DB-backed one
        # must not.
        importlib.reload(guardrails_module)

    response = client.post(
        f"/api/questions/{question['question_id']}/answer",
        json={"response": "a short, within-limit answer"},
    )
    assert response.status_code == 429, response.text
    body = response.json()
    assert body["error"] == "rate_limited"
    assert body["retry_after_seconds"] > 0
