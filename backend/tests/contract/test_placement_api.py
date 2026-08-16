"""Contract test: placement endpoints match contracts/api.md (T027).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise. Question generation is mocked at the LLM-call boundary
(`_run_agent_once`, see test_placement_determinism.py) so this test
exercises the real API/DB contract without depending on a live LLM
call.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

_FIXED_MC_DRAFT_JSON = (
    '{"question_type": "multiple_choice", "stem": "mock question", '
    '"options": ["a", "b", "c", "d"], "correct_index": 1, '
    '"correct_value": null, "tolerance": null}'
)


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


@pytest.fixture()
def mocked_generation():
    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_FIXED_MC_DRAFT_JSON),
    ):
        yield


def test_start_placement_unknown_subject_returns_404(client, db_session):
    response = client.post("/api/subjects/does-not-exist/placement/start")
    assert response.status_code == 404


def test_start_placement_response_shape(client, demo_learner, algebra_subject, mocked_generation):
    response = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    assert response.status_code == 200
    body = response.json()

    assert "placement_session_id" in body
    assert isinstance(body["questions"], list)
    assert len(body["questions"]) == 2  # algebra-1 has 2 entry-level topics

    for question in body["questions"]:
        assert set(question.keys()) == {
            "question_id",
            "topic_id",
            "difficulty",
            "question_type",
            "stem",
            "options",
        }
        # Every entry-level topic is "unknown" at placement time -> always "easy" (FR-006).
        assert question["difficulty"] == "easy"
        assert "answer_key" not in question


def test_submit_placement_response_shape_and_unknown_topics(
    client, demo_learner, algebra_subject, mocked_generation
):
    start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    questions = start.json()["questions"]
    placement_session_id = start.json()["placement_session_id"]

    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
    submit = client.post(f"/api/placement/{placement_session_id}/submit", json={"answers": answers})
    assert submit.status_code == 200
    body = submit.json()

    mastery_by_topic = {entry["topic_id"]: entry for entry in body["mastery_state"]}
    touched_topic_ids = {q["topic_id"] for q in questions}

    # All 8 algebra-1 topics appear, not just the 2 entry-level ones answered.
    assert len(mastery_by_topic) == 8

    for topic_id, entry in mastery_by_topic.items():
        if topic_id in touched_topic_ids:
            assert entry["status"] == "scored"
            assert isinstance(entry["p_mastery"], float)
            assert entry["band"] in ("struggling", "developing", "mastered")
        else:
            assert entry["status"] == "unknown"
            assert entry["p_mastery"] is None
            assert entry["band"] is None


def test_submit_placement_twice_returns_409(
    client, demo_learner, algebra_subject, mocked_generation
):
    start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    questions = start.json()["questions"]
    placement_session_id = start.json()["placement_session_id"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]

    first = client.post(f"/api/placement/{placement_session_id}/submit", json={"answers": answers})
    assert first.status_code == 200

    second = client.post(f"/api/placement/{placement_session_id}/submit", json={"answers": answers})
    assert second.status_code == 409


def test_submit_placement_wrong_response_shape_returns_422(
    client, demo_learner, algebra_subject, mocked_generation
):
    start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    questions = start.json()["questions"]
    placement_session_id = start.json()["placement_session_id"]

    # All algebra-1 entry-level questions are multiple_choice (mocked) --
    # a string response violates the "integer option index" shape.
    answers = [{"question_id": q["question_id"], "response": "not-an-index"} for q in questions]
    submit = client.post(f"/api/placement/{placement_session_id}/submit", json={"answers": answers})
    assert submit.status_code == 422
