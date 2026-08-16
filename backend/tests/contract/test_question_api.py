"""Contract test: next-question / answer / flag endpoints match
contracts/api.md (T041).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise. Question generation is mocked at the LLM-call boundary
(`_run_agent_once`) so this test exercises the real API/DB contract
without depending on a live LLM call.
"""

import uuid
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


def _complete_placement(client: TestClient, subject_id: str) -> dict:
    start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text
    return submit.json()


def test_next_question_without_placement_returns_404(
    client, db_session, demo_learner, algebra_subject
):
    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 404


def test_next_question_response_shape(client, demo_learner, algebra_subject, mocked_generation):
    _complete_placement(client, algebra_subject.subject_id)

    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "question_id",
        "topic_id",
        "difficulty",
        "question_type",
        "stem",
        "options",
    }
    assert body["difficulty"] in ("easy", "medium", "hard")
    assert "answer_key" not in body


def test_next_question_always_200_across_repeated_requests(
    client, demo_learner, algebra_subject, mocked_generation
):
    """No "no eligible topic" error case exists in this contract -- the
    zero-eligible-topics fallback rule (data-model.md) guarantees a 200
    on every request, never a 409."""
    _complete_placement(client, algebra_subject.subject_id)

    for _ in range(5):
        response = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": algebra_subject.subject_id},
        )
        assert response.status_code == 200


def test_answer_question_response_shape(client, demo_learner, algebra_subject, mocked_generation):
    _complete_placement(client, algebra_subject.subject_id)
    next_question = client.get(
        f"/api/learners/{demo_learner.learner_id}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    ).json()

    response = client.post(
        f"/api/questions/{next_question['question_id']}/answer", json={"response": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "correct",
        "topic_id",
        "prior_p_mastery",
        "posterior_p_mastery",
        "band",
    }
    assert body["band"] in ("struggling", "developing", "mastered")


def test_answer_question_twice_returns_409(
    client, demo_learner, algebra_subject, mocked_generation
):
    _complete_placement(client, algebra_subject.subject_id)
    next_question = client.get(
        f"/api/learners/{demo_learner.learner_id}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    ).json()

    first = client.post(
        f"/api/questions/{next_question['question_id']}/answer", json={"response": 1}
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/questions/{next_question['question_id']}/answer", json={"response": 1}
    )
    assert second.status_code == 409


def test_answer_unknown_question_returns_404(client, db_session):
    response = client.post(f"/api/questions/{uuid.uuid4()}/answer", json={"response": 1})
    assert response.status_code == 404


def test_flag_question_response_shape(client, demo_learner, algebra_subject, mocked_generation):
    _complete_placement(client, algebra_subject.subject_id)
    next_question = client.get(
        f"/api/learners/{demo_learner.learner_id}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    ).json()

    response = client.post(
        f"/api/questions/{next_question['question_id']}/flag",
        json={"flagged_by": str(demo_learner.learner_id), "reason": "wrong answer key"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "question_id": next_question["question_id"],
        "validation_status": "flagged",
    }
