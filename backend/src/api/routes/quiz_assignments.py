"""Instructor-assigned quiz endpoints (spec 011, contracts/api.md).

Instructor-facing create/list/cancel only in this module's initial cut
(User Story 1) -- guardian-facing list/start (User Story 2) and the
per-assignment per-student report (User Story 3) extend this same
router as those stories land.
"""

import datetime
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ForbiddenError, NotFoundError
from src.db import get_db
from src.models.classroom_roster import ClassroomRoster
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.services.auth.dependencies import InstructorAccount, current_instructor
from src.services.quiz_assignment.assignment import cancel_assignment, create_assignment

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
