"""Contract test: `GET /api/learners/{id}/next-question` surfaces its
selection reason (spec 025 User Story 1, FR-001/FR-002).

`is_fallback`/`p_mastery`/`effective_p_mastery` are already computed by
`select_next_topic` (spec 022/024) but were discarded before
`NextQuestionOut` was built -- this test proves they now reach the
response. Requires a reachable `DATABASE_URL` (tests/conftest.py);
question generation is mocked at the LLM-call boundary, same as
`test_question_api.py`.
"""

import datetime

import pytest
from fastapi.testclient import TestClient

from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState

_FIXED_MC_DRAFT_JSON = (
    '{"question_type": "multiple_choice", "stem": "mock question", '
    '"options": ["a", "b", "c", "d"], "correct_index": 1, '
    '"correct_value": null, "tolerance": null}'
)

_ALGEBRA_TOPIC_IDS_IN_ORDER = [
    "integers-and-operations",
    "variables-and-expressions",
    "order-of-operations",
    "solving-one-step-equations",
    "solving-multi-step-equations",
    "linear-inequalities",
    "graphing-linear-equations",
    "systems-of-linear-equations",
]


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


@pytest.fixture()
def mocked_generation():
    from unittest.mock import AsyncMock, patch

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_FIXED_MC_DRAFT_JSON),
    ):
        yield


def _complete_placement(client: TestClient, subject_id: str) -> None:
    start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": 1} for q in questions]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text


def _master_every_topic(db_session, learner_id, subject_id) -> None:
    db_session.add(GradeProgress(learner_id=learner_id, subject_id=subject_id, unlocked_grade=8))
    db_session.commit()
    now = datetime.datetime.now(datetime.UTC)
    for topic_id in _ALGEBRA_TOPIC_IDS_IN_ORDER:
        db_session.add(
            MasteryState(
                learner_id=learner_id,
                subject_id=subject_id,
                topic_id=topic_id,
                p_mastery=0.8,
                update_count=1,
                consecutive_mastered_observations=2,
                updated_at=now,
            )
        )
    db_session.commit()


def test_eligible_pool_pick_reports_is_fallback_false(
    client, db_session, demo_learner, algebra_subject, mocked_generation
):
    _complete_placement(client, algebra_subject.subject_id)

    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_fallback"] is False
    # A never-before-attempted topic has no raw prior -- and no decay
    # applies outside the mastered-fallback pool, so both fields agree.
    assert body["p_mastery"] == body["effective_p_mastery"]


def test_fallback_pick_reports_is_fallback_true_with_both_mastery_fields(
    client, db_session, demo_learner, algebra_subject, mocked_generation
):
    _master_every_topic(db_session, demo_learner.learner_id, algebra_subject.subject_id)

    response = client.get(
        f"/api/learners/{demo_learner.learner_id}/next-question",
        params={"subject_id": algebra_subject.subject_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_fallback"] is True
    assert body["p_mastery"] == 0.8
    # Within the decay grace period -- effective equals raw exactly (FR-006).
    assert body["effective_p_mastery"] == 0.8
    # FR-002: a fallback pick names the actual elapsed-since-practice time.
    assert body["last_practiced_at"] is not None

