"""Instructor-assigned quiz endpoints (spec 011, contracts/api.md).

Instructor-facing create/list/cancel and guardian-facing list/start in
this module -- the per-assignment per-student report (User Story 3)
extends this same router as that story lands.
"""

import datetime
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ForbiddenError, NotFoundError
from src.api.routes.quiz import QuizQuestionOut, QuizStartOut
from src.db import get_db
from src.models.classroom_roster import ClassroomRoster
from src.models.enums import QuizSessionStatus
from src.models.learner_profile import LearnerProfile
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.models.quiz_session import QuizSession
from src.models.real_guardian_account import RealGuardianAccount
from src.observability.session import get_database_session_service
from src.services.auth.dependencies import InstructorAccount, current_guardian, current_instructor
from src.services.quiz.session import compute_quiz_summary, persist_quiz_question
from src.services.quiz_assignment.assignment import (
    cancel_assignment,
    create_assignment,
    start_assignment_attempt,
)
from src.services.quiz_assignment.status import derive_target_status

router = APIRouter()


def _get_owned_roster(
    db: Session, roster_id: uuid.UUID, instructor: InstructorAccount
) -> ClassroomRoster:
    """Mirrors `rosters.py`'s `_get_owned_roster` (FR-004)."""
    roster = db.get(ClassroomRoster, roster_id)
    if roster is None:
        raise NotFoundError("unknown roster_id")
    if roster.instructor_id != instructor.instructor_id:
        raise ForbiddenError("not_roster_owner")
    return roster


def _get_owned_assignment(
    db: Session, roster_id: uuid.UUID, assignment_id: uuid.UUID, instructor: InstructorAccount
) -> QuizAssignment:
    _get_owned_roster(db, roster_id, instructor)
    assignment = db.get(QuizAssignment, assignment_id)
    if assignment is None or assignment.roster_id != roster_id:
        raise NotFoundError("unknown assignment_id")
    return assignment


class CreateAssignmentIn(BaseModel):
    topic_ids: list[str]
    question_count: int
    due_at: datetime.datetime | None = None
    learner_ids: list[uuid.UUID] | Literal["all"]


class CreateAssignmentOut(BaseModel):
    assignment_id: uuid.UUID
    roster_id: uuid.UUID
    subject_id: str
    topic_ids: list[str]
    question_count: int
    due_at: datetime.datetime | None
    target_learner_ids: list[uuid.UUID]


@router.post(
    "/api/rosters/{roster_id}/assignments", response_model=CreateAssignmentOut, status_code=201
)
def create_assignment_route(
    roster_id: uuid.UUID,
    body: CreateAssignmentIn,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> CreateAssignmentOut:
    roster = _get_owned_roster(db, roster_id, instructor)
    assignment = create_assignment(
        db,
        roster=roster,
        instructor_id=instructor.instructor_id,
        topic_ids=body.topic_ids,
        question_count=body.question_count,
        due_at=body.due_at,
        learner_ids=body.learner_ids,
    )
    targets = (
        db.query(QuizAssignmentTarget)
        .filter(QuizAssignmentTarget.assignment_id == assignment.assignment_id)
        .order_by(QuizAssignmentTarget.created_at)
        .all()
    )
    target_learner_ids = [target.learner_id for target in targets]
    return CreateAssignmentOut(
        assignment_id=assignment.assignment_id,
        roster_id=assignment.roster_id,
        subject_id=assignment.subject_id,
        topic_ids=assignment.topic_ids,
        question_count=assignment.question_count,
        due_at=assignment.due_at,
        target_learner_ids=target_learner_ids,
    )


class AssignmentSummaryOut(BaseModel):
    assignment_id: uuid.UUID
    topic_ids: list[str]
    question_count: int
    due_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    created_at: datetime.datetime


class ListAssignmentsOut(BaseModel):
    assignments: list[AssignmentSummaryOut]


@router.get("/api/rosters/{roster_id}/assignments", response_model=ListAssignmentsOut)
def list_roster_assignments_route(
    roster_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> ListAssignmentsOut:
    _get_owned_roster(db, roster_id, instructor)
    assignments = (
        db.query(QuizAssignment)
        .filter(QuizAssignment.roster_id == roster_id)
        .order_by(QuizAssignment.created_at)
        .all()
    )
    return ListAssignmentsOut(
        assignments=[
            AssignmentSummaryOut(
                assignment_id=a.assignment_id,
                topic_ids=a.topic_ids,
                question_count=a.question_count,
                due_at=a.due_at,
                cancelled_at=a.cancelled_at,
                created_at=a.created_at,
            )
            for a in assignments
        ]
    )


@router.delete("/api/rosters/{roster_id}/assignments/{assignment_id}", status_code=204)
def cancel_assignment_route(
    roster_id: uuid.UUID,
    assignment_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> None:
    assignment = _get_owned_assignment(db, roster_id, assignment_id, instructor)
    cancel_assignment(db, assignment=assignment)


class LearnerScoreOut(BaseModel):
    correct: int
    total: int


class AssignmentLearnerReportOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    status: str
    score: LearnerScoreOut | None


class AssignmentDetailOut(BaseModel):
    assignment_id: uuid.UUID
    topic_ids: list[str]
    question_count: int
    due_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    learners: list[AssignmentLearnerReportOut]


@router.get(
    "/api/rosters/{roster_id}/assignments/{assignment_id}", response_model=AssignmentDetailOut
)
def get_assignment_detail_route(
    roster_id: uuid.UUID,
    assignment_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> AssignmentDetailOut:
    """Per-student status/score (FR-009, FR-010) -- a direct query, not
    routed through the Recommendation Agent (research.md §5): "did this
    learner complete this assignment" is a different question from that
    agent's weak-area analysis."""
    assignment = _get_owned_assignment(db, roster_id, assignment_id, instructor)

    rows = (
        db.query(QuizAssignmentTarget, LearnerProfile)
        .join(LearnerProfile, LearnerProfile.learner_id == QuizAssignmentTarget.learner_id)
        .filter(QuizAssignmentTarget.assignment_id == assignment_id)
        .order_by(QuizAssignmentTarget.created_at)
        .all()
    )

    quiz_session_ids = [
        target.quiz_session_id for target, _learner in rows if target.quiz_session_id is not None
    ]
    status_by_session_id: dict[uuid.UUID, QuizSessionStatus] = {}
    if quiz_session_ids:
        for quiz_session_id, status in (
            db.query(QuizSession.quiz_session_id, QuizSession.status)
            .filter(QuizSession.quiz_session_id.in_(quiz_session_ids))
            .all()
        ):
            status_by_session_id[quiz_session_id] = status

    learners_out: list[AssignmentLearnerReportOut] = []
    for target, learner in rows:
        session_status = (
            status_by_session_id.get(target.quiz_session_id)
            if target.quiz_session_id is not None
            else None
        )
        status = derive_target_status(session_status)
        score: LearnerScoreOut | None = None
        if status in ("completed", "ended_early"):
            summary = compute_quiz_summary(db, quiz_session_id=target.quiz_session_id)
            score = LearnerScoreOut(correct=summary.score.correct, total=summary.score.total)
        learners_out.append(
            AssignmentLearnerReportOut(
                learner_id=learner.learner_id,
                display_name=learner.display_name,
                status=status,
                score=score,
            )
        )

    return AssignmentDetailOut(
        assignment_id=assignment.assignment_id,
        topic_ids=assignment.topic_ids,
        question_count=assignment.question_count,
        due_at=assignment.due_at,
        cancelled_at=assignment.cancelled_at,
        learners=learners_out,
    )


def _get_own_learner(
    db: Session, learner_id: uuid.UUID, guardian: RealGuardianAccount
) -> LearnerProfile:
    """Mirrors `rosters.py`'s `join_roster_route` ownership check."""
    learner = db.get(LearnerProfile, learner_id)
    if learner is None or learner.guardian_id != guardian.guardian_id:
        raise ForbiddenError("not_your_learner")
    return learner


class AssignmentForLearnerOut(BaseModel):
    assignment_id: uuid.UUID
    topic_ids: list[str]
    question_count: int
    due_at: datetime.datetime | None
    cancelled_at: datetime.datetime | None
    status: str


class ListLearnerAssignmentsOut(BaseModel):
    assignments: list[AssignmentForLearnerOut]


@router.get("/api/learners/{learner_id}/assignments", response_model=ListLearnerAssignmentsOut)
def list_learner_assignments_route(
    learner_id: uuid.UUID,
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> ListLearnerAssignmentsOut:
    _get_own_learner(db, learner_id, guardian)

    rows = (
        db.query(QuizAssignmentTarget, QuizAssignment)
        .join(QuizAssignment, QuizAssignment.assignment_id == QuizAssignmentTarget.assignment_id)
        .filter(QuizAssignmentTarget.learner_id == learner_id)
        .order_by(QuizAssignment.created_at)
        .all()
    )

    quiz_session_ids = [
        target.quiz_session_id for target, _assignment in rows if target.quiz_session_id is not None
    ]
    status_by_session_id: dict[uuid.UUID, QuizSessionStatus] = {}
    if quiz_session_ids:
        for quiz_session_id, status in (
            db.query(QuizSession.quiz_session_id, QuizSession.status)
            .filter(QuizSession.quiz_session_id.in_(quiz_session_ids))
            .all()
        ):
            status_by_session_id[quiz_session_id] = status

    # FR-016: every assignment targeting this learner is included, a
    # cancelled one included and marked via `cancelled_at` rather than
    # omitted (research.md §8) -- `status` is derived purely from
    # quiz-session state, never folded together with `cancelled_at`.
    return ListLearnerAssignmentsOut(
        assignments=[
            AssignmentForLearnerOut(
                assignment_id=assignment.assignment_id,
                topic_ids=assignment.topic_ids,
                question_count=assignment.question_count,
                due_at=assignment.due_at,
                cancelled_at=assignment.cancelled_at,
                status=derive_target_status(
                    status_by_session_id.get(target.quiz_session_id)
                    if target.quiz_session_id is not None
                    else None
                ),
            )
            for target, assignment in rows
        ]
    )


@router.post(
    "/api/assignments/{assignment_id}/learners/{learner_id}/start",
    response_model=QuizStartOut,
    status_code=201,
)
async def start_assignment_attempt_route(
    assignment_id: uuid.UUID,
    learner_id: uuid.UUID,
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> QuizStartOut:
    _get_own_learner(db, learner_id, guardian)

    assignment = db.get(QuizAssignment, assignment_id)
    if assignment is None:
        raise NotFoundError("unknown assignment_id")

    target = (
        db.query(QuizAssignmentTarget)
        .filter(
            QuizAssignmentTarget.assignment_id == assignment_id,
            QuizAssignmentTarget.learner_id == learner_id,
        )
        .first()
    )
    if target is None:
        raise ForbiddenError("not_targeted")

    quiz, result = await start_assignment_attempt(
        db, assignment=assignment, target=target, session_service=get_database_session_service()
    )
    if result is None:
        return QuizStartOut(quiz_session_id=quiz.quiz_session_id, status="ended_early")

    question = persist_quiz_question(
        db,
        quiz_session_id=quiz.quiz_session_id,
        learner_id=learner_id,
        subject_id=assignment.subject_id,
        result=result,
    )
    db.commit()
    return QuizStartOut(
        quiz_session_id=quiz.quiz_session_id,
        status="in_progress",
        question=QuizQuestionOut(
            question_id=question.question_id,
            topic_id=result.topic_id,
            difficulty=result.difficulty.value,
            question_type=result.question_type.value,
            stem=result.draft.stem,
            options=result.draft.options,
        ),
    )
