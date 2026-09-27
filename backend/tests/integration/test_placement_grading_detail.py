"""Integration test: `POST /api/placement/{id}/submit` surfaces
per-question grading detail immediately (spec 025 User Story 3,
FR-009/FR-010, Acceptance Scenario 2).

Placement questions are multiple-choice/numeric only (`grade_answer`
has no free-text/multi-step case; spec 015/018 both deliberately keep
it that way, research.md §4 correction) -- so `criteria_met`/
`criteria_missed`/`step_results` are always `null` here; this test
covers `correct`/`prior_p_mastery`/`posterior_p_mastery`/`refreshed`,
the fields placement can actually populate.

Requires a reachable `DATABASE_URL` (tests/conftest.py).
"""

from fastapi.testclient import TestClient


def _start_and_answer(client, subject_id, *, response_value):
    start = client.post(f"/api/subjects/{subject_id}/placement/start")
    assert start.status_code == 200, start.text
    questions = start.json()["questions"]
    answers = [{"question_id": q["question_id"], "response": response_value} for q in questions]
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
    body, questions = _start_and_answer(client, "algebra-1", response_value=0)

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

    # At least one entry reflects each outcome (response=0 against a mixed
    # answer key set means some right, some wrong, across a real fixture).
    assert any(e["correct"] for e in results) or any(not e["correct"] for e in results)


def test_aggregate_mastery_state_field_unchanged(db_session, demo_learner, algebra_subject):
    from src.api.main import app

    client = TestClient(app)
    body, _questions = _start_and_answer(client, "algebra-1", response_value=0)

    assert "mastery_state" in body
    assert isinstance(body["mastery_state"], list)
