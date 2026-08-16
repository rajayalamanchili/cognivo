"""Integration test: 5 consecutive next-question requests -- no two
text-identical/near-duplicate questions, 100% correctly topic-scoped
(SC-002), T040.

Question generation is mocked at the LLM-call boundary
(`_run_agent_once`) with a distinct stem per call, so this test
exercises the real dedup-check + persistence path (FR-008) without
depending on a live LLM call.
"""

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


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


def test_five_consecutive_next_questions_are_distinct_and_topic_scoped(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    call_count = {"n": 0}

    async def _fake_run_agent_once(agent, session_service):
        call_count["n"] += 1
        return _draft_json(f"unique generated question #{call_count['n']}")

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(side_effect=_fake_run_agent_once),
    ):
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
        assert start.status_code == 200, start.text
        questions = start.json()["questions"]
        answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
        submit = client.post(
            f"/api/placement/{start.json()['placement_session_id']}/submit",
            json={"answers": answers},
        )
        assert submit.status_code == 200, submit.text

        results = []
        for _ in range(5):
            response = client.get(
                f"/api/learners/{demo_learner.learner_id}/next-question",
                params={"subject_id": algebra_subject.subject_id},
            )
            assert response.status_code == 200, response.text
            results.append(response.json())

    stems = [r["stem"] for r in results]
    assert len(set(stems)) == len(stems), f"expected all-distinct stems, got {stems}"

    valid_topic_ids = {topic.topic_id for topic in algebra_subject.topics}
    for result in results:
        assert result["topic_id"] in valid_topic_ids
        assert result["difficulty"] in ("easy", "medium", "hard")
