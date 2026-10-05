"""Integration test: placement AND practice (`next-question`) work for
the two new pilot subjects exactly as they do for Algebra I (spec 040
User Story 1, FR-005, tasks.md T007).

Mirrors `test_placement.py`'s existing mocking convention (fixed
multiple-choice draft at the LLM-call boundary) -- every algebra-2/
physics grade-entry topic is multiple_choice/numeric (research.md
Decision 1), same precondition `test_placement.py` relies on for
algebra-1.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.usefixtures("database_available")

_FIXED_MC_DRAFT_JSON = (
    '{"question_type": "multiple_choice", "stem": "mock question", '
    '"options": ["a", "b", "c", "d"], "correct_index": 1, '
    '"correct_value": null, "tolerance": null}'
)
_CORRECT_RESPONSE = 1  # matches _FIXED_MC_DRAFT_JSON's correct_index


def _client():
    from src.api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def _patch_generation():
    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_FIXED_MC_DRAFT_JSON),
    )


@pytest.mark.parametrize("subject_fixture", ["algebra_2_subject", "physics_subject"])
def test_placement_through_mastery_update_identical_to_algebra_1(
    request, demo_learner, subject_fixture
):
    subject = request.getfixturevalue(subject_fixture)
    client = _client()

    with _patch_generation():
        start = client.post(f"/api/subjects/{subject.subject_id}/placement/start")
    assert start.status_code == 200, start.text
    body = start.json()
    questions = body["questions"]
    assert questions

    placement_session_id = body["placement_session_id"]
    answers = [{"question_id": q["question_id"], "response": _CORRECT_RESPONSE} for q in questions]
    submit = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    mastery = client.get(
        f"/api/learners/{demo_learner.learner_id}/mastery-state",
        params={"subject_id": subject.subject_id},
    )
    assert mastery.status_code == 200, mastery.text
    assert mastery.json()["topics"]

    # Practice entry point (FR-005 covers both placement AND practice):
    # placement above already unlocked at least one eligible topic, so
    # next-question must succeed exactly as it does for algebra-1.
    with _patch_generation():
        next_question = client.get(
            f"/api/learners/{demo_learner.learner_id}/next-question",
            params={"subject_id": subject.subject_id},
        )
    assert next_question.status_code == 200, next_question.text

    answer = client.post(
        f"/api/questions/{next_question.json()['question_id']}/answer",
        json={"response": _CORRECT_RESPONSE},
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["posterior_p_mastery"] is not None
