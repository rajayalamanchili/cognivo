"""spec 020's cascade-delete executor (FR-002/FR-003/FR-004): given a
pending `DeletionRequest`, walks data-model.md's ordered cascade tables
for its `target_type` inside a single DB transaction, then marks the
request completed. An explicit, application-level walk rather than a
DB-level `ON DELETE CASCADE` (research.md R2) -- Principle V needs a
hook point to reason about what's removed, and
`generated_questions.flagged_by` needs `SET NULL`, not delete, when it
points at a *different*, still-existing learner's owned question.

Every per-table operation below is a bulk `.delete()`/`.update()` (never
an ORM-object load-then-delete), which is what makes an
already-partially-or-fully-deleted target a safe no-op rather than an
error (spec.md Edge Cases: a target gone by the time the cron reaches
it is marked completed, not retried forever) -- a `DELETE ... WHERE`
matching zero rows is not a failure.
"""

import datetime
import os
import uuid

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.classroom_roster import ClassroomRoster
from src.models.deletion_request import DeletionRequest
from src.models.enrollment import Enrollment
from src.models.enrollment_request import EnrollmentRequest
from src.models.enums import DeletionTargetType, RetentionAccountType
from src.models.generated_question import GeneratedQuestion
from src.models.grade_progress import GradeProgress
from src.models.learner_profile import LearnerProfile
from src.models.mastery_state import MasteryState
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.models.quiz_session import QuizSession
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.models.retention_record import RetentionRecord
from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession

# research.md R1, tech-stack.md's cron batch size cap precedent
# (Misconception Classifier's MAX_PAIRS_PER_RUN).
MAX_DELETIONS_PER_RUN = int(os.environ.get("DELETION_MAX_PER_RUN", "20"))


def execute_deletion(db: Session, deletion_request: DeletionRequest) -> None:
    """Runs the cascade for `deletion_request.target_type`, then sets
    `completed_at`, all inside one transaction: either every step and
    the completion timestamp commit together, or an exception rolls
    back the whole thing and the request stays pending (`completed_at`
    stays `NULL`) for the next run to retry in full (FR-003)."""
    dispatch = {
        DeletionTargetType.LEARNER: _delete_learner,
        DeletionTargetType.GUARDIAN: _delete_guardian,
        DeletionTargetType.INSTRUCTOR: _delete_instructor,
    }
    try:
        dispatch[deletion_request.target_type](db, deletion_request.target_id)
        deletion_request.completed_at = datetime.datetime.now(datetime.UTC)
        db.commit()
    except Exception:
        db.rollback()
        raise


def _delete_learner(db: Session, target_learner_id: uuid.UUID) -> None:
    learner = db.get(LearnerProfile, target_learner_id)
    if learner is None:
        return  # already deleted / never existed -- nothing to cascade

    guardian_id = learner.guardian_id
    retention_record_id = learner.retention_record_id

    session_ids = [
        row[0]
        for row in db.query(TutoringSession.session_id)
        .filter(TutoringSession.learner_id == target_learner_id)
        .all()
    ]
    if session_ids:
        db.query(TutorExchange).filter(TutorExchange.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
    db.query(TutoringSession).filter(TutoringSession.learner_id == target_learner_id).delete(
        synchronize_session=False
    )

    db.query(QuizAssignmentTarget).filter(
        QuizAssignmentTarget.learner_id == target_learner_id
    ).delete(synchronize_session=False)

    db.query(AssessmentEvent).filter(AssessmentEvent.learner_id == target_learner_id).delete(
        synchronize_session=False
    )

    # A question flagged by this learner but owned by someone else
    # survives -- only the reference to the deleted flagger is cleared
    # (research.md R2).
    db.query(GeneratedQuestion).filter(
        GeneratedQuestion.flagged_by == target_learner_id,
        GeneratedQuestion.learner_id != target_learner_id,
    ).update({GeneratedQuestion.flagged_by: None}, synchronize_session=False)

    db.query(GeneratedQuestion).filter(GeneratedQuestion.learner_id == target_learner_id).delete(
        synchronize_session=False
    )

    db.query(MasteryState).filter(MasteryState.learner_id == target_learner_id).delete(
        synchronize_session=False
    )
    db.query(EnrollmentRequest).filter(EnrollmentRequest.learner_id == target_learner_id).delete(
        synchronize_session=False
    )
    db.query(Enrollment).filter(Enrollment.learner_id == target_learner_id).delete(
        synchronize_session=False
    )
    db.query(GradeProgress).filter(GradeProgress.learner_id == target_learner_id).delete(
        synchronize_session=False
    )
    db.query(QuizSession).filter(QuizSession.learner_id == target_learner_id).delete(
        synchronize_session=False
    )

    db.query(LearnerProfile).filter(LearnerProfile.learner_id == target_learner_id).delete(
        synchronize_session=False
    )

    if retention_record_id is not None:
        db.query(RetentionRecord).filter(
            RetentionRecord.retention_record_id == retention_record_id
        ).delete(synchronize_session=False)

    if guardian_id is not None:
        remaining_learners = (
            db.query(LearnerProfile).filter(LearnerProfile.guardian_id == guardian_id).count()
        )
        if remaining_learners == 0:
            _delete_guardian(db, guardian_id)


def _delete_guardian(db: Session, guardian_id: uuid.UUID) -> None:
    guardian = db.get(RealGuardianAccount, guardian_id)
    if guardian is None:
        return

    linked_learner_ids = [
        row[0]
        for row in db.query(LearnerProfile.learner_id)
        .filter(LearnerProfile.guardian_id == guardian_id)
        .all()
    ]
    for learner_id in linked_learner_ids:
        _delete_learner(db, learner_id)

    db.query(RealGuardianAccount).filter(RealGuardianAccount.guardian_id == guardian_id).delete(
        synchronize_session=False
    )


def _delete_instructor(db: Session, instructor_id: uuid.UUID) -> None:
    instructor = db.get(RealInstructorAccount, instructor_id)
    if instructor is None:
        return

    # Rosters remaining at this point were never transferred (a
    # transfer, done synchronously at submission time, already moved
    # both classroom_rosters.instructor_id and quiz_assignments.
    # instructor_id to the successor -- data-model.md's instructor
    # cascade step 1) -- so everything found here is scoped for
    # deletion, never reassignment.
    roster_ids = [
        row[0]
        for row in db.query(ClassroomRoster.roster_id)
        .filter(ClassroomRoster.instructor_id == instructor_id)
        .all()
    ]
    if roster_ids:
        assignment_ids = [
            row[0]
            for row in db.query(QuizAssignment.assignment_id)
            .filter(QuizAssignment.roster_id.in_(roster_ids))
            .all()
        ]
        if assignment_ids:
            db.query(QuizAssignmentTarget).filter(
                QuizAssignmentTarget.assignment_id.in_(assignment_ids)
            ).delete(synchronize_session=False)
        db.query(QuizAssignment).filter(QuizAssignment.roster_id.in_(roster_ids)).delete(
            synchronize_session=False
        )
        db.query(Enrollment).filter(Enrollment.roster_id.in_(roster_ids)).delete(
            synchronize_session=False
        )
        db.query(EnrollmentRequest).filter(EnrollmentRequest.roster_id.in_(roster_ids)).delete(
            synchronize_session=False
        )
        db.query(ClassroomRoster).filter(ClassroomRoster.roster_id.in_(roster_ids)).delete(
            synchronize_session=False
        )

    db.query(RealInstructorAccount).filter(
        RealInstructorAccount.instructor_id == instructor_id
    ).delete(synchronize_session=False)

    db.query(RetentionRecord).filter(
        RetentionRecord.account_type == RetentionAccountType.INSTRUCTOR,
        RetentionRecord.account_id == instructor_id,
    ).delete(synchronize_session=False)
