"""Integration test: the opt-in-nudges "new activity" indicator (spec
019 FR-006/FR-007/FR-007a/FR-008, contracts/api.md, research.md
Decision 7).

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


def _complete_one_question_attempt(client, db_session, algebra_subject, *, label, unlocked_grade):
    instructor_email = f"viewed-indicator-instructor-{label}@example.com"
    guardian_email = f"viewed-indicator-guardian-{label}@example.com"

    register_instructor(client, instructor_email)
    roster_id, join_code = create_roster(client, subject_id=algebra_subject.subject_id)
    client.post("/api/auth/logout")

    guardian_id, learner_id = register_guardian_with_learner(
        client, guardian_email=guardian_email, learner_name=f"Learner {label}"
    )
    join_response = client.post(
        "/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code}
    )
    assert join_response.status_code == 201, join_response.text

    db_session.add(
        GradeProgress(
            learner_id=learner_id,
            subject_id=algebra_subject.subject_id,
            unlocked_grade=unlocked_grade,
        )
    )
    db_session.commit()

    client.post("/api/auth/logout")
    login_instructor(client, instructor_email)
    assignment = create_assignment(
        client,
        roster_id=roster_id,
        topic_ids=[ENTRY_TOPIC],
        question_count=1,
        learner_ids=[learner_id],
    )
    client.post("/api/auth/logout")

    login_guardian(client, guardian_email)
    with patch_generation():
        start = client.post(
            f"/api/assignments/{assignment['assignment_id']}/learners/{learner_id}/start"
        )
    assert start.status_code == 201, start.text
    question_id = start.json()["question"]["question_id"]

    answer = client.post(f"/api/questions/{question_id}/answer", json={"response": 0})
    assert answer.status_code == 200, answer.text

    return {
        "quiz_session_id": start.json()["quiz_session_id"],
        "guardian_email": guardian_email,
        "learner_id": learner_id,
    }


def _has_unviewed_activity(client, learner_id):
    response = client.get(f"/api/learners/{learner_id}/assignments")
    assert response.status_code == 200, response.text
    assignments = response.json()["assignments"]
    assert len(assignments) == 1
    assert assignments[0]["status"] == "completed"
    return assignments[0]["has_unviewed_activity"]


@pytest.mark.parametrize(
    "unlocked_grade,expect_indicator",
    [(4, False), (7, True), (10, False)],
)
def test_indicator_exclusive_to_opt_in_nudges_tier(
    client, db_session, algebra_subject, unlocked_grade, expect_indicator
):
    attempt = _complete_one_question_attempt(
        client,
        db_session,
        algebra_subject,
        label=f"grade-{unlocked_grade}",
        unlocked_grade=unlocked_grade,
    )
    # Still logged in as the guardian from the attempt above.
    assert _has_unviewed_activity(client, attempt["learner_id"]) is expect_indicator


def test_viewing_the_summary_clears_the_indicator_and_is_idempotent(
    client, db_session, algebra_subject
):
    attempt = _complete_one_question_attempt(
        client, db_session, algebra_subject, label="clears", unlocked_grade=7
    )
    assert _has_unviewed_activity(client, attempt["learner_id"]) is True

    summary = client.get(f"/api/quizzes/{attempt['quiz_session_id']}")
    assert summary.status_code == 200, summary.text
    assert _has_unviewed_activity(client, attempt["learner_id"]) is False

    # A second view must not change anything further (idempotent).
    summary_again = client.get(f"/api/quizzes/{attempt['quiz_session_id']}")
    assert summary_again.status_code == 200, summary_again.text
    assert _has_unviewed_activity(client, attempt["learner_id"]) is False


def test_check_in_and_independent_targets_still_record_guardian_viewed_at(
    client, db_session, algebra_subject
):
    """The column write is tier-independent (research.md Decision 7) --
    only the badge's *exposure* is opt-in-nudges-only."""
    from src.models.quiz_assignment_target import QuizAssignmentTarget

    for unlocked_grade in (4, 10):
        attempt = _complete_one_question_attempt(
            client,
            db_session,
            algebra_subject,
            label=f"viewed-write-{unlocked_grade}",
            unlocked_grade=unlocked_grade,
        )
        target = (
            db_session.query(QuizAssignmentTarget)
            .filter(QuizAssignmentTarget.quiz_session_id == attempt["quiz_session_id"])
            .first()
        )
        assert target.guardian_viewed_at is None

        summary = client.get(f"/api/quizzes/{attempt['quiz_session_id']}")
        assert summary.status_code == 200, summary.text

        db_session.refresh(target)
        assert target.guardian_viewed_at is not None
