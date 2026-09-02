"""Integration test: a generated question's persisted row records the
Assessment-Generation prompt's exact version (spec 014 FR-009, US3).

Question generation is mocked at the LLM-call boundary
(`_run_agent_once`), same as test_next_question_variety.py, so this
exercises the real persistence path without depending on a live call.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.agents.assessment_gen.agent import GENERATION_PROMPT_VERSION
from src.models.generated_question import GeneratedQuestion


def _draft_json(stem: str) -> str:
    return json.dumps(
        {
            "question_type": "multiple_choice",
            "stem": stem,
            "options": ["a", "b", "c", "d"],
            "correct_index": 1,
            "correct_value": None,
            "tolerance": None,
        }
    )


def test_placement_question_records_generation_prompt_version(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)

    async def _fake_run_agent_once(agent, session_service):
        return _draft_json("a placement question")

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    ):
        response = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")

    assert response.status_code == 200, response.text
    question_id = response.json()["questions"][0]["question_id"]

    question = db_session.get(GeneratedQuestion, question_id)
    assert question.generation_prompt_version == GENERATION_PROMPT_VERSION
    assert question.generation_prompt_version is not None
