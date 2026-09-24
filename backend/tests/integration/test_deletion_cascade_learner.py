"""Integration test: submitting and executing a deletion request for a
learner hard-deletes every row in data-model.md's learner cascade, and
every read path Acceptance Scenario 2 names degrades cleanly afterward
-- never a 500, never a dangling/partial record (spec 020 FR-002/FR-004,
SC-001). Also confirms the `DeletionRequest` row itself survives its own
cascade (FR-010).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import uuid

import pytest

from src.models.assessment_event import AssessmentEvent
from src.models.deletion_request import DeletionRequest
from src.models.enums import (
    AssessmentEventType,
    DeletionTargetType,
    DifficultyBand,
    EnrollmentMode,
    QuestionType,
    QuizSessionStatus,
    ValidationStatus,
)
from src.models.generated_question import GeneratedQuestion
from src.models.learner_profile import LearnerProfile
from src.models.mastery_state import MasteryState
from src.models.practice_session import PracticeSession
from src.models.quiz_session import QuizSession
from src.models.real_guardian_account import RealGuardianAccount
from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession

pytestmark = pytest.mark.usefixtures("database_available")


@pytest.fixture()
def instructor_client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


@pytest.fixture()
def guardian_client(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.main import app

    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")
    return TestClient(app, base_url="https://testserver")


def test_learner_deletion_cascades_fully_and_read_paths_degrade_cleanly(
    instructor_client, guardian_client, db_session, algebra_subject, monkeypatch
):
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    subject_id = algebra_subject.subject_id
    topic_id = algebra_subject.topics[0].topic_id

    # 1. Instructor creates an open roster.
    instructor_register = instructor_client.post(
        "/api/auth/instructor/register",
        json={"email": f"instructor-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert instructor_register.status_code == 201, instructor_register.text

    roster_response = instructor_client.post(
        "/api/rosters",
        json={"subject_id": subject_id, "enrollment_mode": EnrollmentMode.OPEN.value},
    )
    assert roster_response.status_code == 201, roster_response.text
    roster = roster_response.json()

    # 2. Guardian registers, adds a learner, and joins the open roster.
    guardian_register = guardian_client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert guardian_register.status_code == 201, guardian_register.text

    learner_response = guardian_client.post("/api/learners", json={"display_name": "Deletable"})
    assert learner_response.status_code == 201, learner_response.text
    learner_id = uuid.UUID(learner_response.json()["learner_id"])

    join_response = guardian_client.post(
        "/api/rosters/join",
        json={"learner_id": str(learner_id), "join_code": roster["join_code"]},
    )
    assert join_response.status_code == 201, join_response.text

    # A second, still-active sibling learner under the same guardian, so
    # the guardian itself is NOT auto-deleted as a side effect (research.md R4).
    sibling_response = guardian_client.post("/api/learners", json={"display_name": "Sibling"})
    assert sibling_response.status_code == 201, sibling_response.text
    sibling_id = uuid.UUID(sibling_response.json()["learner_id"])

    # 3. Seed the rest of the cascade directly.
    db_session.add(
        MasteryState(learner_id=learner_id, subject_id=subject_id, topic_id=topic_id, p_mastery=0.4)
    )
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem="1 + 1 = ?",
        options=["1", "2", "3", "4"],
        answer_key={"correct_index": 1},
        validation_status=ValidationStatus.FLAGGED,
        flagged_by=learner_id,
        flagged_reason="looked off",
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    db_session.add(
        AssessmentEvent(
            learner_id=learner_id,
            event_type=AssessmentEventType.ANSWER_SUBMITTED,
            question_id=question.question_id,
            subject_id=subject_id,
            topic_id=topic_id,
            payload={"correct": True},
        )
    )
    quiz_session = QuizSession(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_ids=[topic_id],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
    )
    db_session.add(quiz_session)
    # Spec 022: practice_sessions carries the same learner_id FK shape.
    practice_session = PracticeSession(
        learner_id=learner_id,
        subject_id=subject_id,
        time_limit_seconds=1800,
        status=QuizSessionStatus.IN_PROGRESS,
    )
    db_session.add(practice_session)
    db_session.commit()
    db_session.refresh(quiz_session)
    db_session.refresh(practice_session)
    quiz_session_id = quiz_session.quiz_session_id
    practice_session_id = practice_session.practice_session_id
    tutoring_session = TutoringSession(learner_id=learner_id, subject_id=subject_id)
    db_session.add(tutoring_session)
    db_session.commit()
    db_session.refresh(tutoring_session)
    tutoring_session_id = tutoring_session.session_id
    db_session.add(
        TutorExchange(session_id=tutoring_session_id, question_text="why?", answer_text="because")
    )
    db_session.commit()
    question_id = question.question_id

    # Sanity: the flagged question shows up in the instructor's queue before deletion.
    flagged_before = instructor_client.get("/api/content-review/flagged")
    assert flagged_before.status_code == 200, flagged_before.text
    assert any(
        entry["question_id"] == str(question_id) for entry in flagged_before.json()["flagged"]
    )

    # 4. Guardian submits the deletion request, then the cron executor processes it.
    submit = guardian_client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": str(learner_id)}
    )
    assert submit.status_code == 201, submit.text
    deletion_request_id = uuid.UUID(submit.json()["deletion_request_id"])

    execute = instructor_client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert execute.status_code == 200, execute.text
    assert execute.json()["processed_count"] >= 1

    db_session.expunge_all()

    # 5. Every cascade row is gone; the sibling learner is untouched.
    assert db_session.get(LearnerProfile, learner_id) is None
    assert db_session.query(MasteryState).filter(MasteryState.learner_id == learner_id).count() == 0
    assert (
        db_session.query(AssessmentEvent).filter(AssessmentEvent.learner_id == learner_id).count()
        == 0
    )
    assert (
        db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.learner_id == learner_id)
        .count()
        == 0
    )
    assert db_session.get(TutoringSession, tutoring_session_id) is None
    assert db_session.get(QuizSession, quiz_session_id) is None
    assert db_session.get(PracticeSession, practice_session_id) is None
    assert db_session.get(LearnerProfile, sibling_id) is not None

    # 6. Read paths named in Acceptance Scenario 2 all degrade cleanly.
    recommendations = guardian_client.get(
        f"/api/learners/{learner_id}/recommendations",
        params={"subject_id": subject_id},
    )
    assert recommendations.status_code == 404, recommendations.text

    mastery_state = guardian_client.get(
        f"/api/learners/{learner_id}/mastery-state",
        params={"subject_id": subject_id},
    )
    assert mastery_state.status_code == 200, mastery_state.text

    enrollments = instructor_client.get(f"/api/rosters/{roster['roster_id']}/enrollments")
    assert enrollments.status_code == 200, enrollments.text
    assert all(
        entry["learner_id"] != str(learner_id) for entry in enrollments.json()["enrollments"]
    )

    flagged_after = instructor_client.get("/api/content-review/flagged")
    assert flagged_after.status_code == 200, flagged_after.text
    assert all(
        entry["question_id"] != str(question_id) for entry in flagged_after.json()["flagged"]
    )

    # 7. The DeletionRequest itself is the one row this feature never deletes.
    reloaded_request = db_session.get(DeletionRequest, deletion_request_id)
    assert reloaded_request is not None
    assert reloaded_request.completed_at is not None


def test_instructor_deleting_last_learner_queues_traceable_guardian_deletion(
    instructor_client, guardian_client, algebra_subject, db_session, monkeypatch
):
    """When the learner deleted (here, by an instructor -- the least
    obvious trigger, since the guardian never requested anything) is
    their guardian's only remaining learner, the guardian's account
    isn't deleted inline as a side effect of this cascade -- it's queued
    as its own traceable `DeletionRequest` (PR #79 review, Constitution
    Principle V) for the executor's next pass to pick up and run through
    the normal, logged path."""
    monkeypatch.setenv("CRON_SECRET", "the-real-secret")
    subject_id = algebra_subject.subject_id

    instructor_register = instructor_client.post(
        "/api/auth/instructor/register",
        json={"email": f"instructor-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert instructor_register.status_code == 201, instructor_register.text

    roster_response = instructor_client.post(
        "/api/rosters",
        json={"subject_id": subject_id, "enrollment_mode": EnrollmentMode.OPEN.value},
    )
    assert roster_response.status_code == 201, roster_response.text
    roster = roster_response.json()

    guardian_register = guardian_client.post(
        "/api/auth/guardian/register",
        json={"email": f"guardian-{uuid.uuid4()}@example.com", "password": "correct horse"},
    )
    assert guardian_register.status_code == 201, guardian_register.text
    guardian_id = uuid.UUID(guardian_register.json()["guardian_id"])

    learner_response = guardian_client.post("/api/learners", json={"display_name": "Only Child"})
    assert learner_response.status_code == 201, learner_response.text
    learner_id = uuid.UUID(learner_response.json()["learner_id"])

    join_response = guardian_client.post(
        "/api/rosters/join",
        json={"learner_id": str(learner_id), "join_code": roster["join_code"]},
    )
    assert join_response.status_code == 201, join_response.text

    submit = instructor_client.post(
        "/api/deletion-requests", json={"target_type": "learner", "target_id": str(learner_id)}
    )
    assert submit.status_code == 201, submit.text

    first_run = instructor_client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert first_run.status_code == 200, first_run.text

    db_session.expunge_all()

    # The learner is gone, but the guardian is untouched by this same
    # pass -- only a new pending request for it now exists.
    assert db_session.get(LearnerProfile, learner_id) is None
    assert db_session.get(RealGuardianAccount, guardian_id) is not None

    queued = (
        db_session.query(DeletionRequest)
        .filter(
            DeletionRequest.target_type == DeletionTargetType.GUARDIAN,
            DeletionRequest.target_id == guardian_id,
        )
        .one()
    )
    assert queued.requested_by == "system:last-learner-cascade"
    assert queued.completed_at is None

    second_run = instructor_client.get(
        "/api/cron/execute-deletions", headers={"Authorization": "Bearer the-real-secret"}
    )
    assert second_run.status_code == 200, second_run.text

    db_session.expunge_all()
    assert db_session.get(RealGuardianAccount, guardian_id) is None
    assert db_session.get(DeletionRequest, queued.deletion_request_id).completed_at is not None
