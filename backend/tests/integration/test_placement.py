"""Integration tests: grade-banded placement (spec 017 FR-002/FR-003,
User Story 1, T015/T016).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise. Question generation is mocked at the LLM-call boundary
(`_run_agent_once`), matching this suite's existing convention (e.g.
test_placement_determinism.py) -- every algebra-1 grade-entry topic is
multiple_choice (content/algebra-1/subject.yaml), so one fixed draft
covers every question this file generates.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.grade_progress import GradeProgress

_FIXED_MC_DRAFT_JSON = (
    '{"question_type": "multiple_choice", "stem": "mock question", '
    '"options": ["a", "b", "c", "d"], "correct_index": 1, '
    '"correct_value": null, "tolerance": null}'
)
_CORRECT_RESPONSE = 1  # matches _FIXED_MC_DRAFT_JSON's correct_index
_INCORRECT_RESPONSE = 0


def _client() -> TestClient:
    from src.api.main import app

    return TestClient(app)


def _patch_generation():
    return patch(
        "src.agents.assessment_gen.agent._run_agent_once",
        new=AsyncMock(return_value=_FIXED_MC_DRAFT_JSON),
    )


def test_start_placement_spans_multiple_grades_each_labeled(demo_learner, algebra_subject):
    client = _client()

    with _patch_generation():
        response = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")

    assert response.status_code == 200, response.text
    questions = response.json()["questions"]

    grades = {q["grade"] for q in questions}
    assert grades == {6, 7, 8}  # more than one grade band (FR-002)
    assert all(q["grade"] is not None for q in questions)


def test_start_placement_against_ungraded_subject_has_null_grades(demo_learner, biology_subject):
    client = _client()

    with _patch_generation():
        response = client.post(f"/api/subjects/{biology_subject.subject_id}/placement/start")

    assert response.status_code == 200, response.text
    questions = response.json()["questions"]

    assert questions  # biology still has entry-level topics
    assert all(q["grade"] is None for q in questions)  # SC-005: unchanged from today


def test_submit_placement_all_correct_assigns_the_highest_declared_grade(
    db_session, demo_learner, algebra_subject
):
    client = _client()

    with _patch_generation():
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    body = start.json()
    placement_session_id = body["placement_session_id"]
    questions = body["questions"]

    answers = [{"question_id": q["question_id"], "response": _CORRECT_RESPONSE} for q in questions]
    submit = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    events = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.GRADE_ASSIGNED,
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].payload["starting_grade"] == 8
    assert events[0].payload["placement_session_id"] == placement_session_id
    assert events[0].payload["correct_by_grade"] == {"6": True, "7": True, "8": True}

    progress = db_session.get(GradeProgress, (demo_learner.learner_id, algebra_subject.subject_id))
    assert progress is not None
    assert progress.unlocked_grade == 8


def test_submit_placement_partial_correct_floors_at_the_last_fully_correct_grade(
    db_session, demo_learner, algebra_subject
):
    client = _client()

    with _patch_generation():
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    body = start.json()
    placement_session_id = body["placement_session_id"]
    questions = body["questions"]

    # Grade 8's sole entry topic (systems-of-linear-equations) answered
    # incorrectly; grades 6 and 7 all correct.
    answers = [
        {
            "question_id": q["question_id"],
            "response": _INCORRECT_RESPONSE
            if q["topic_id"] == "systems-of-linear-equations"
            else _CORRECT_RESPONSE,
        }
        for q in questions
    ]
    submit = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == demo_learner.learner_id,
            AssessmentEvent.event_type == AssessmentEventType.GRADE_ASSIGNED,
        )
        .one()
    )
    assert event.payload["starting_grade"] == 7
    assert event.payload["correct_by_grade"] == {"6": True, "7": True, "8": False}

    progress = db_session.get(GradeProgress, (demo_learner.learner_id, algebra_subject.subject_id))
    assert progress.unlocked_grade == 7


def test_submit_placement_against_ungraded_subject_assigns_no_grade(
    db_session, demo_learner, biology_subject
):
    client = _client()

    with _patch_generation():
        start = client.post(f"/api/subjects/{biology_subject.subject_id}/placement/start")
    body = start.json()
    questions = body["questions"]

    answers = [{"question_id": q["question_id"], "response": _CORRECT_RESPONSE} for q in questions]
    submit = client.post(
        f"/api/placement/{body['placement_session_id']}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.GRADE_ASSIGNED)
        .all()
    )
    assert events == []
    assert (
        db_session.get(GradeProgress, (demo_learner.learner_id, biology_subject.subject_id))
        is None
    )
