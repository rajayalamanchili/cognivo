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
from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.generated_question import GeneratedQuestion
from src.models.grade_progress import GradeProgress
from tests.integration.quiz_assignment_helpers import (
    login_guardian,
    register_guardian_with_learner,
)

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


def test_submit_placement_survives_a_concurrent_grade_assignment_race(
    db_session, demo_learner, algebra_subject, monkeypatch
):
    """Two `submit_placement` calls racing to assign the same learner/
    subject's starting grade would otherwise both pass the `db.get(
    GradeProgress, ...)` pre-check before either commits -- the second
    insert then hits the `(learner_id, subject_id)` primary key and must
    not surface as an unhandled 500, nor discard this request's own
    answer/mastery events (spec 017 PR #67 review). Simulated here by
    monkeypatching the existence check to miss a row that (as a stand-in
    for a concurrent winner) already exists in the DB.
    """
    client = _client()

    with _patch_generation():
        start = client.post(f"/api/subjects/{algebra_subject.subject_id}/placement/start")
    body = start.json()
    placement_session_id = body["placement_session_id"]
    questions = body["questions"]

    db_session.add(
        GradeProgress(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            unlocked_grade=6,
        )
    )
    db_session.commit()

    real_get = Session.get

    def racy_get(self, entity, ident, *args, **kwargs):
        if entity is GradeProgress:
            return None
        return real_get(self, entity, ident, *args, **kwargs)

    monkeypatch.setattr(Session, "get", racy_get)

    answers = [{"question_id": q["question_id"], "response": _CORRECT_RESPONSE} for q in questions]
    submit = client.post(
        f"/api/placement/{placement_session_id}/submit", json={"answers": answers}
    )
    assert submit.status_code == 200, submit.text

    # The pre-existing ("concurrent winner's") grade is untouched, and
    # this request's own answers were still recorded despite the race.
    monkeypatch.undo()
    progress = db_session.get(GradeProgress, (demo_learner.learner_id, algebra_subject.subject_id))
    assert progress.unlocked_grade == 6
    answered = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED)
        .all()
    )
    assert len(answered) == len(questions)


def test_start_placement_with_real_learner_id_assigns_questions_to_that_learner(
    db_session, algebra_subject, monkeypatch
):
    """spec 044 FR-025, US5: a guardian's own real learner can start
    placement directly, same gating pattern as start_practice_session
    (research.md §2)."""
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    from src.api.main import app

    client = TestClient(app, base_url="https://testserver")
    _, learner_id = register_guardian_with_learner(
        client, guardian_email="placement-start-owner@example.com", learner_name="Real Learner"
    )

    with _patch_generation():
        start = client.post(
            f"/api/subjects/{algebra_subject.subject_id}/placement/start",
            params={"learner_id": learner_id},
        )
    assert start.status_code == 200, start.text

    questions = start.json()["questions"]
    assert questions
    for question in questions:
        row = db_session.get(GeneratedQuestion, question["question_id"])
        assert str(row.learner_id) == learner_id


def test_start_placement_for_another_guardians_learner_is_forbidden(
    db_session, algebra_subject, monkeypatch
):
    """spec 044 FR-025: ownership-gated exactly like start_practice_session."""
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    from src.api.main import app

    client = TestClient(app, base_url="https://testserver")
    _, owner_learner_id = register_guardian_with_learner(
        client, guardian_email="placement-start-owner-b@example.com", learner_name="Owned"
    )
    client.post("/api/auth/logout")

    register_guardian_with_learner(
        client, guardian_email="placement-start-intruder@example.com", learner_name="Other"
    )
    login_guardian(client, "placement-start-intruder@example.com")

    start = client.post(
        f"/api/subjects/{algebra_subject.subject_id}/placement/start",
        params={"learner_id": owner_learner_id},
    )
    assert start.status_code == 403, start.text
    assert start.json() == {"detail": "not_your_learner"}
