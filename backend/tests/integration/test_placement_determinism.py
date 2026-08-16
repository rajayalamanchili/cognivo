"""Integration test: placement determinism (SC-001), T024.

Re-runs identical scripted placement answers, submitted in the same
order, 10x against a freshly-reset learner state each time, and asserts
the resulting mastery output (p_mastery/band per topic) is byte-
identical. Question *generation* text (the Assessment-Generation
Agent's LLM call) is mocked at the LLM-call boundary
(`_run_agent_once`) to a fixed deterministic draft -- SC-001 is a claim
about the mastery MODEL's determinism (BKT + grading + persistence)
given identical answers, not a claim that an LLM call itself is
reproducible, which research.md never asserts. Everything downstream of
that mock (validation/retry logic, DB writes, BKT update, API response
shaping) runs for real against a live Postgres instance.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState

_FIXED_DRAFT_JSON = (
    '{"question_type": "multiple_choice", "stem": "mock question", '
    '"options": ["a", "b", "c", "d"], "correct_index": 1, '
    '"correct_value": null, "tolerance": null}'
)


def _reset_learner_state(db_session, learner_id: uuid.UUID) -> None:
    """Wipes a learner's mastery/question/event history between
    iterations -- test-only privileged reset, standing in for "a fresh
    placement session" (quickstart.md); never a runtime application
    code path (MasteryState/AssessmentEvent rows are otherwise
    append-only/never-deleted, per data-model.md)."""
    db_session.query(AssessmentEvent).filter(AssessmentEvent.learner_id == learner_id).delete()
    db_session.query(MasteryState).filter(MasteryState.learner_id == learner_id).delete()
    db_session.query(GeneratedQuestion).filter(GeneratedQuestion.learner_id == learner_id).delete()
    db_session.commit()


def _run_one_placement(client: TestClient, subject_id: str) -> dict:
    start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    body = start.json()

    # Deterministic scripted pattern: correct for the first question in
    # topic order, incorrect for every other -- exercises both BKT
    # update directions per run.
    answers = [
        {"question_id": q["question_id"], "response": 1 if i == 0 else 0}
        for i, q in enumerate(body["questions"])
    ]

    submit = client.post(
        f"/api/placement/{body['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text
    return submit.json()


def _strip_to_mastery_fields(mastery_state: list[dict]) -> list[dict]:
    return [
        {key: entry[key] for key in ("topic_id", "status", "p_mastery", "band")}
        for entry in mastery_state
    ]


def test_placement_determinism(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)

    with patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_FIXED_DRAFT_JSON),
    ):
        results = []
        for _ in range(10):
            _reset_learner_state(db_session, demo_learner.learner_id)
            result = _run_one_placement(client, algebra_subject.subject_id)
            results.append(_strip_to_mastery_fields(result["mastery_state"]))

    first = results[0]
    assert all(result == first for result in results), results
    assert any(entry["status"] == "scored" for entry in first)
