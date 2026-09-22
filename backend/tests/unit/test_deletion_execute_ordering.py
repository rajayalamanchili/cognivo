"""Unit tests: `backend/src/services/deletion/execute.py`'s
`_delete_learner` cascade order (spec 020 FR-002/FR-004, data-model.md).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime
import uuid

from src.models.assessment_event import AssessmentEvent
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enrollment_request import EnrollmentRequest
from src.models.enums import (
    AssessmentEventType,
    AuthorizedByType,
    DifficultyBand,
    EnrollmentMode,
    QuestionType,
    QuizSessionStatus,
    RetentionAccountType,
    RetentionEnrollmentStatus,
    ValidationStatus,
)
from src.models.generated_question import GeneratedQuestion
from src.models.grade_progress import GradeProgress
from src.models.learner_profile import LearnerProfile
from src.models.mastery_state import MasteryState
from src.models.quiz_session import QuizSession
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.models.retention_record import RetentionRecord
from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession
from src.services.deletion.execute import _delete_guardian, _delete_learner


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _make_guardian(db_session) -> RealGuardianAccount:
    guardian = RealGuardianAccount(
        email=f"guardian-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(guardian)
    db_session.commit()
    db_session.refresh(guardian)
    return guardian


def _make_instructor(db_session) -> RealInstructorAccount:
    instructor = RealInstructorAccount(
        email=f"instructor-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(instructor)
    db_session.commit()
    db_session.refresh(instructor)
    return instructor


def _make_real_learner(db_session, *, guardian_id: uuid.UUID) -> LearnerProfile:
    retention_record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=uuid.uuid4(),  # placeholder, corrected below once learner exists
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=guardian_id,
        enrollment_status=RetentionEnrollmentStatus.ACTIVE,
    )
    db_session.add(retention_record)
    db_session.commit()
    db_session.refresh(retention_record)

    learner = LearnerProfile(
        display_name="Test Real Learner",
        is_demo=False,
        guardian_id=guardian_id,
        retention_record_id=retention_record.retention_record_id,
    )
    db_session.add(learner)
    db_session.commit()
    db_session.refresh(learner)

    retention_record.account_id = learner.learner_id
    db_session.commit()
    return learner


def test_cascade_removes_every_seeded_table_without_integrity_error(db_session, algebra_subject):
    guardian = _make_guardian(db_session)
    other_guardian = _make_guardian(db_session)
    instructor = _make_instructor(db_session)
    learner = _make_real_learner(db_session, guardian_id=guardian.guardian_id)
    other_learner = _make_real_learner(db_session, guardian_id=other_guardian.guardian_id)
    topic = algebra_subject.topics[0]

    roster = ClassroomRoster(
        instructor_id=instructor.instructor_id,
        subject_id=algebra_subject.subject_id,
        enrollment_mode=EnrollmentMode.CLOSED,
    )
    db_session.add(roster)
    db_session.commit()
    db_session.refresh(roster)

    db_session.add(
        Enrollment(
            learner_id=learner.learner_id,
            roster_id=roster.roster_id,
            authorized_by_type=AuthorizedByType.INSTRUCTOR,
            authorized_by_id=instructor.instructor_id,
        )
    )
    db_session.add(EnrollmentRequest(learner_id=learner.learner_id, roster_id=roster.roster_id))
    db_session.add(
        MasteryState(
            learner_id=learner.learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id=topic.topic_id,
            p_mastery=0.5,
        )
    )
    db_session.add(
        GradeProgress(
            learner_id=learner.learner_id, subject_id=algebra_subject.subject_id, unlocked_grade=1
        )
    )
    quiz_session = QuizSession(
        learner_id=learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
    )
    db_session.add(quiz_session)
    db_session.commit()
    db_session.refresh(quiz_session)

    owned_question = GeneratedQuestion(
        learner_id=learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem="2 + 2 = ?",
        options=["3", "4", "5", "6"],
        answer_key={"correct_index": 1},
        validation_status=ValidationStatus.VALID,
        quiz_session_id=quiz_session.quiz_session_id,
    )
    db_session.add(owned_question)

    # A question owned by a DIFFERENT, still-existing learner, flagged by
    # the one about to be deleted -- must survive with flagged_by cleared,
    # not be deleted (research.md R2).
    other_owned_question = GeneratedQuestion(
        learner_id=other_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem="3 + 3 = ?",
        options=["5", "6", "7", "8"],
        answer_key={"correct_index": 1},
        validation_status=ValidationStatus.FLAGGED,
        flagged_by=learner.learner_id,
        flagged_reason="seemed wrong",
    )
    db_session.add(other_owned_question)
    db_session.commit()
    db_session.refresh(owned_question)
    db_session.refresh(other_owned_question)

    db_session.add(
        AssessmentEvent(
            learner_id=learner.learner_id,
            event_type=AssessmentEventType.ANSWER_SUBMITTED,
            question_id=owned_question.question_id,
            subject_id=algebra_subject.subject_id,
            topic_id=topic.topic_id,
            payload={"correct": True},
        )
    )

    tutoring_session = TutoringSession(
        learner_id=learner.learner_id,
        guardian_id=guardian.guardian_id,
        subject_id=algebra_subject.subject_id,
    )
    db_session.add(tutoring_session)
    db_session.commit()
    db_session.refresh(tutoring_session)

    db_session.add(
        TutorExchange(
            session_id=tutoring_session.session_id,
            question_text="why?",
            answer_text="because",
        )
    )
    db_session.commit()

    learner_id = learner.learner_id
    retention_record_id = learner.retention_record_id
    other_learner_id = other_learner.learner_id
    other_question_id = other_owned_question.question_id
    quiz_session_id = quiz_session.quiz_session_id
    tutoring_session_id = tutoring_session.session_id

    _delete_learner(db_session, learner_id)
    db_session.commit()
    db_session.expunge_all()  # bulk deletes bypass the identity map (synchronize_session=False)

    assert db_session.get(LearnerProfile, learner_id) is None
    assert db_session.get(RetentionRecord, retention_record_id) is None
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
    assert db_session.query(Enrollment).filter(Enrollment.learner_id == learner_id).count() == 0
    assert (
        db_session.query(EnrollmentRequest)
        .filter(EnrollmentRequest.learner_id == learner_id)
        .count()
        == 0
    )
    assert (
        db_session.query(GradeProgress).filter(GradeProgress.learner_id == learner_id).count() == 0
    )
    assert db_session.get(QuizSession, quiz_session_id) is None
    assert db_session.get(TutoringSession, tutoring_session_id) is None
    assert (
        db_session.query(TutorExchange)
        .filter(TutorExchange.session_id == tutoring_session_id)
        .count()
        == 0
    )

    # The other learner's own question survives, flagged_by cleared, not deleted.
    surviving = db_session.get(GeneratedQuestion, other_question_id)
    assert surviving is not None
    assert surviving.flagged_by is None
    assert db_session.get(LearnerProfile, other_learner_id) is not None


def test_delete_guardian_clears_orphaned_tutoring_session_guardian_id(
    db_session, algebra_subject
):
    """SC-001 gate column-granularity (PR #79 review): `tutoring_sessions.
    guardian_id` is a distinct FK from `tutoring_sessions.learner_id`
    and isn't automatically cleared by the learner-scoped delete in
    `_delete_learner` -- a session belonging to a still-existing learner
    (owned by a different guardian) but stamped with this guardian's id
    must not be left as a dangling reference once the guardian is gone."""
    guardian_to_delete = _make_guardian(db_session)
    other_guardian = _make_guardian(db_session)
    other_learner = _make_real_learner(db_session, guardian_id=other_guardian.guardian_id)

    stale_session = TutoringSession(
        learner_id=other_learner.learner_id,
        guardian_id=guardian_to_delete.guardian_id,
        subject_id=algebra_subject.subject_id,
    )
    db_session.add(stale_session)
    db_session.commit()
    db_session.refresh(stale_session)
    stale_session_id = stale_session.session_id

    guardian_id = guardian_to_delete.guardian_id
    other_learner_id = other_learner.learner_id

    _delete_guardian(db_session, guardian_id)
    db_session.commit()
    db_session.expunge_all()

    assert db_session.get(RealGuardianAccount, guardian_id) is None
    assert db_session.get(LearnerProfile, other_learner_id) is not None
    reloaded_session = db_session.get(TutoringSession, stale_session_id)
    assert reloaded_session is not None
    assert reloaded_session.guardian_id is None
