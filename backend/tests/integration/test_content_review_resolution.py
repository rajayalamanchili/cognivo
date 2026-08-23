"""Integration test: resolving a flagged question (`reactivate` or
`reject`) updates `validation_status` accordingly and records an
audited event with the resolving instructor, action, and timestamp
(FR-012/FR-013, SC-003, T044).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, QuestionType, ValidationStatus
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


def _register_guardian_with_learner(client, email, display_name):
    response = client.post(
        "/api/auth/guardian/register", json={"email": email, "password": "correct horse"}
    )
    assert response.status_code == 201, response.text
    learner = client.post("/api/learners", json={"display_name": display_name})
    assert learner.status_code == 201, learner.text
    return response.json()["guardian_id"], learner.json()["learner_id"]


def _seed_and_flag_question(client, db_session, *, learner_id: str, subject) -> str:
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

    flag = client.post(
        f"/api/questions/{question.question_id}/flag",
        json={"flagged_by": learner_id, "reason": "wrong answer key"},
    )
    assert flag.status_code == 200, flag.text
    return str(question.question_id)


def _setup_roster_with_flagged_question(client, db_session, algebra_subject, instructor_email):
    instructor_id = _register_instructor(client, instructor_email)
    roster = client.post(
        "/api/rosters", json={"subject_id": algebra_subject.subject_id, "enrollment_mode": "open"}
    )
    join_code = roster.json()["join_code"]

    client.post("/api/auth/logout")
    _, learner_id = _register_guardian_with_learner(client, "parent-l@example.com", "Learner L")
    client.post("/api/rosters/join", json={"learner_id": learner_id, "join_code": join_code})

    question_id = _seed_and_flag_question(
        client, db_session, learner_id=learner_id, subject=algebra_subject
    )

    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/instructor/login",
        json={"email": instructor_email, "password": "correct horse"},
    )
    assert response.status_code == 200

    return instructor_id, question_id


def test_reactivate_sets_validation_status_valid_and_records_event(
    client, db_session, algebra_subject
):
    instructor_id, question_id = _setup_roster_with_flagged_question(
        client, db_session, algebra_subject, "instructor-l@example.com"
    )

    response = client.post(
        f"/api/content-review/{question_id}/resolve", json={"action": "reactivate"}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"question_id": question_id, "validation_status": "valid"}

    db_session.expire_all()
    question = db_session.get(GeneratedQuestion, uuid.UUID(question_id))
    assert question.validation_status == ValidationStatus.VALID

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == uuid.UUID(question_id),
            AssessmentEvent.event_type == AssessmentEventType.CONTENT_REVIEW_RESOLVED,
        )
        .one()
    )
    assert event.payload["action"] == "reactivate"
    assert event.payload["resolved_by_instructor_id"] == instructor_id
    assert event.created_at is not None


def test_reject_leaves_validation_status_flagged_and_records_event(
    client, db_session, algebra_subject
):
    instructor_id, question_id = _setup_roster_with_flagged_question(
        client, db_session, algebra_subject, "instructor-m@example.com"
    )

    response = client.post(f"/api/content-review/{question_id}/resolve", json={"action": "reject"})
    assert response.status_code == 200, response.text
    assert response.json() == {"question_id": question_id, "validation_status": "flagged"}

    db_session.expire_all()
    question = db_session.get(GeneratedQuestion, uuid.UUID(question_id))
    assert question.validation_status == ValidationStatus.FLAGGED

    event = (
        db_session.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == uuid.UUID(question_id),
            AssessmentEvent.event_type == AssessmentEventType.CONTENT_REVIEW_RESOLVED,
        )
        .one()
    )
    assert event.payload["action"] == "reject"
    assert event.payload["resolved_by_instructor_id"] == instructor_id


def test_resolve_question_not_on_your_roster_returns_403(client, db_session, algebra_subject):
    _, question_id = _setup_roster_with_flagged_question(
        client, db_session, algebra_subject, "instructor-n@example.com"
    )

    client.post("/api/auth/logout")
    _register_instructor(client, "instructor-o@example.com")

    response = client.post(
        f"/api/content-review/{question_id}/resolve", json={"action": "reactivate"}
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "not_learner_on_your_roster"}


def test_resolve_unknown_question_returns_404(client):
    _register_instructor(client, "instructor-p@example.com")
    response = client.post(
        f"/api/content-review/{uuid.uuid4()}/resolve", json={"action": "reactivate"}
    )
    assert response.status_code == 404
