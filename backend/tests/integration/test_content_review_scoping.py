"""Integration test: the flagged-question queue is scoped via an
`Enrollment` join at query time -- a flagged question for a learner
outside the instructor's roster(s) never appears (quickstart scenario
8, FR-011, research.md §5, T043).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.enums import DifficultyBand, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def _register_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    return response.json()["instructor_id"]


def _login_instructor(client, email):
    response = client.post(
        "/api/auth/instructor/login", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 200, response.text


def _register_guardian_with_learner(client, email, display_name):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def _seed_question(db_session, *, learner_id: str, subject) -> str:
    topic = subject.topics[0]
    question = GeneratedQuestion(
        learner_id=uuid.UUID(learner_id),
        subject_id=subject.subject_id,
        topic_id=topic.topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem=f"seeded question {uuid.uuid4().hex[:8]}",
        options=["a", "b", "c", "d"],
        answer_key={"correct_index": 0},
        validation_status=ValidationStatus.VALID,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return str(question.question_id)


def test_flagged_queue_excludes_learners_outside_instructors_rosters(
    client, db_session, algebra_subject
):
    _register_instructor(client, "instructor-j@example.com")
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    roster_id = roster.json()["roster_id"]
    join_code = roster.json()["join_code"]

    client.post("/api/auth/logout")
    _, in_roster_learner_id = _register_guardian_with_learner(
        client, "parent-in@example.com", "In Roster"
    )
    join = client.post(
        "/api/rosters/join", json={"learner_id": in_roster_learner_id, "join_code": join_code}
    )
    assert join.status_code == 201, join.text

    client.post("/api/auth/logout")
    _, outside_learner_id = _register_guardian_with_learner(
        client, "parent-out@example.com", "Outside Roster"
    )
    # Not joined to any roster.

    in_roster_question_id = _seed_question(
        db_session, learner_id=in_roster_learner_id, subject=algebra_subject
    )
    outside_question_id = _seed_question(
        db_session, learner_id=outside_learner_id, subject=algebra_subject
    )

    flag_in = client.post(
        f"/api/questions/{in_roster_question_id}/flag",
        json={"flagged_by": in_roster_learner_id, "reason": "wrong answer key"},
    )
    assert flag_in.status_code == 200, flag_in.text
    flag_out = client.post(
        f"/api/questions/{outside_question_id}/flag",
        json={"flagged_by": outside_learner_id, "reason": "wrong answer key"},
    )
    assert flag_out.status_code == 200, flag_out.text

    client.post("/api/auth/logout")
    _login_instructor(client, "instructor-j@example.com")

    response = client.get("/api/content-review/flagged")
    assert response.status_code == 200, response.text
    flagged_ids = {entry["question_id"] for entry in response.json()["flagged"]}
    assert flagged_ids == {in_roster_question_id}
    assert outside_question_id not in flagged_ids

    entry = next(e for e in response.json()["flagged"] if e["question_id"] == in_roster_question_id)
    assert entry["learner_id"] == in_roster_learner_id
    assert entry["roster_id"] == roster_id
    assert entry["flagged_reason"] == "wrong answer key"
    assert entry["flagged_at"]


def test_flagged_queue_empty_is_not_an_error(client):
    _register_instructor(client, "instructor-k@example.com")
    response = client.get("/api/content-review/flagged")
    assert response.status_code == 200
    assert response.json() == {"flagged": []}
