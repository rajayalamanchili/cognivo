"""Integration test: `POST /api/placement/{id}/submit` surfaces
per-question grading detail immediately (spec 025 User Story 3,
FR-009/FR-010, Acceptance Scenario 2).

Placement questions are multiple-choice/numeric only (`grade_answer`
has no free-text/multi-step case; spec 015/018 both deliberately keep
it that way, research.md §4 correction) -- so `criteria_met`/
`criteria_missed`/`step_results` are always `null` here; this test
covers `correct`/`prior_p_mastery`/`posterior_p_mastery`/`refreshed`,
the fields placement can actually populate.

Question generation is mocked at the LLM-call boundary
(`_run_agent_once`), matching this suite's existing convention (e.g.
test_placement.py, test_placement_determinism.py) rather than hitting
a real model -- CI has no `ANTHROPIC_API_KEY` configured.

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

_FIXED_MC_DRAFT_JSON = (
    '{"question_type": "multiple_choice", "stem": "mock question", '
    '"options": ["a", "b", "c", "d"], "correct_index": 1, '
    '"correct_value": null, "tolerance": null}'
)
_CORRECT_RESPONSE = 1  # matches _FIXED_MC_DRAFT_JSON's correct_index
_INCORRECT_RESPONSE = 0


def _patch_generation():
    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_FIXED_MC_DRAFT_JSON),
    )


def _start_and_answer(client, subject_id):
    with _patch_generation():
        start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    # Alternate correct/incorrect responses so the assertion below covers
    # both outcomes without depending on a real, varied answer key.
    answers = [
        {
            "question_id": q["question_id"],
            "response": _CORRECT_RESPONSE if i % 2 == 0 else _INCORRECT_RESPONSE,
        }
        for i, q in enumerate(questions)
    ]
    submit = client.post(
        f"/api/placement/{start.json()['placement_session_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200, submit.text
    return submit.json(), questions


def test_per_question_results_present_for_a_passing_and_failing_answer(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    body, questions = _start_and_answer(client, "algebra-1")

    results = body["per_question_results"]
    assert len(results) == len(questions)

    question_ids = {q["question_id"] for q in questions}
    for entry in results:
        assert entry["question_id"] in question_ids
        assert isinstance(entry["correct"], bool)
        assert isinstance(entry["posterior_p_mastery"], float)
        # Placement is MC/numeric-only -- never a fabricated rubric.
        assert entry["criteria_met"] is None
        assert entry["criteria_missed"] is None
        assert entry["step_results"] is None
        assert isinstance(entry["refreshed"], bool)

    assert any(e["correct"] for e in results)
    assert any(not e["correct"] for e in results)


def test_aggregate_mastery_state_field_unchanged(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    body, _questions = _start_and_answer(client, "algebra-1")

    assert "mastery_state" in body
    assert isinstance(body["mastery_state"], list)
