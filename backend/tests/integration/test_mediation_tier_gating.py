"""Integration tests: guardian-mediation tier gating and the hand-off
token (spec 019 FR-004/FR-005a/b/c, contracts/api.md, Acceptance
Scenarios 1-5).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from src.models.grade_progress import GradeProgress
from tests.integration.quiz_assignment_helpers import (
    ENTRY_TOPIC,
    create_assignment,
    create_roster,
    login_guardian,
    login_instructor,
    register_guardian_with_learner,
    register_instructor,
)
from tests.integration.quiz_helpers import patch_generation

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _set_unlocked_grade(db_session, *, learner_id, subject_id, unlocked_grade):
    db_session.add(
        GradeProgress(learner_id=learner_id, subject_id=subject_id, unlocked_grade=unlocked_grade)
    )
    db_session.commit()


def _start_for_grade(client, db_session, algebra_subject, *, grade, question_count=2, label=None):
    """One instructor + roster + a single guardian/learner pair placed
    at `grade`, targeted by an assignment, with the guardian logged in
    and the attempt started. Returns (start_response_json, guardian_email)."""
    suffix = label or f"grade-{grade}"
    instructor_email = f"tier-gating-instructor-{suffix}@example.com"
    guardian_email = f"tier-gating-guardian-{suffix}@example.com"

    register_instructor(client, instructor_email)
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)
    client.post("/api/auth/logout")

    guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email=guardian_email, learner_name=f"Learner {suffix}"
    )
    join_response = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert join_response.status_code == 201, join_response.text

    _set_unlocked_grade(
        db_session,
        learner_id=learner_id,
        subject_id=algebra_subject.subject_id,
        unlocked_grade=grade,
    )

    client.post("/api/auth/logout")
    login_instructor(client, instructor_email)
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        question_count=question_count,
        learner_ids=[learner_id],
    )
    client.post("/api/auth/logout")

    login_guardian(client, guardian_email)
    with patch_generation():
        start = client.post(
            f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
        )
    assert start.status_code == 201, start.text
    return start.json(), guardian_email


def test_co_present_tier_issues_no_handoff_token_and_requires_guardian(
    client, db_session, algebra_subject
):
    body, _guardian_email = _start_for_grade(client, db_session, algebra_subject, grade=2)
    assert body["handoff_token"] is None

    quiz_session_id = body["quiz_session_id"]
    client.post("/api/auth/logout")
    response = client.get(f"/api/quizzes/{quiz_session_id}/next-question")
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "not_learner_guardian"}


@pytest.mark.parametrize("grade", [4, 7, 10])
def test_other_tiers_issue_a_handoff_token_usable_without_a_guardian_session(
    client, db_session, algebra_subject, grade
):
    body, _guardian_email = _start_for_grade(client, db_session, algebra_subject, grade=grade)
    handoff_token = body["handoff_token"]
    assert handoff_token is not None

    quiz_session_id = body["quiz_session_id"]
    question_id = body["question"]["question_id"]

    client.post("/api/auth/logout")

    answer = client.post(
        f"/api/questions/{question_id}/answer",
        json={"response": 0},
        headers={"X-Quiz-Handoff-Token": handoff_token},
    )
    assert answer.status_code == 200, answer.text

    with patch_generation():
        next_question = client.get(
            f"/api/quizzes/{quiz_session_id}/next-question",
            headers={"X-Quiz-Handoff-Token": handoff_token},
        )
    assert next_question.status_code == 200, next_question.text
    assert next_question.json()["status"] == "in_progress"


def test_handoff_token_rejected_for_a_different_quiz_session(client, db_session, algebra_subject):
    body_a, _ = _start_for_grade(client, db_session, algebra_subject, grade=7, label="diff-a")
    body_b, _ = _start_for_grade(client, db_session, algebra_subject, grade=7, label="diff-b")

    client.post("/api/auth/logout")
    response = client.get(
        f"/api/quizzes/{body_b['quiz_session_id']}/next-question",
        headers={"X-Quiz-Handoff-Token": body_a["handoff_token"]},
    )
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": "invalid_handoff_token"}


def test_handoff_token_rejected_once_quiz_session_is_no_longer_in_progress(
    client, db_session, algebra_subject
):
    body, _guardian_email = _start_for_grade(
        client, db_session, algebra_subject, grade=10, question_count=1
    )
    handoff_token = body["handoff_token"]
    question_id = body["question"]["question_id"]
    quiz_session_id = body["quiz_session_id"]

    client.post("/api/auth/logout")
    answer = client.post(
        f"/api/questions/{question_id}/answer",
        json={"response": 0},
        headers={"X-Quiz-Handoff-Token": handoff_token},
    )
    assert answer.status_code == 200, answer.text

    response = client.get(
        f"/api/quizzes/{quiz_session_id}/next-question",
        headers={"X-Quiz-Handoff-Token": handoff_token},
    )
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "quiz_session_not_in_progress"}
