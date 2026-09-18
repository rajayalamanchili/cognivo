"""Integration test: `GET /api/learners/{id}/next-question` for a
step_grading_enabled-configured topic carries an ordered list of step
prompts before display, with no answer_key leaked to the client (spec
018 FR-001, FR-002), T011. Mirrors
`test_free_text_question_generation.py`.
"""

from src.models.generated_question import GeneratedQuestion
from tests.integration.multi_step_helpers import (
    MULTI_STEP_TOPIC_ID,
    get_multi_step_question,
)


def test_next_question_is_multi_step_with_persisted_step_rubric(
    db_session, demo_learner, algebra_subject
):
    from fastapi.testclient import TestClient

    from src.api.main import app

    client = TestClient(app)
    body = get_multi_step_question(client, db_session, demo_learner, algebra_subject)

    assert body["topic_id"] == MULTI_STEP_TOPIC_ID
    assert body["question_type"] == "multi_step"
    assert body["options"] is None
    assert body["steps"] == [
        "Isolate the variable term on one side.",
        "Solve for x.",
    ]
    # No rubric criteria in the client-facing response -- only prompts.
    assert "answer_key" not in body
    assert "criteria" not in body

    question = db_session.get(GeneratedQuestion, body["question_id"])
    assert question is not None
    steps = question.answer_key["steps"]
    assert len(steps) == 2
    for step in steps:
        assert step["step_prompt"]
        assert len(step["criteria"]) >= 2
        for criterion in step["criteria"]:
            assert criterion["description"]
            assert criterion["weight"] > 0
