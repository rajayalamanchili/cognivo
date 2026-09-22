"""Real-account deletion request submission and status check (spec 020
contracts/api.md "POST/GET /api/deletion-requests") -- FR-001/FR-006/
FR-007/FR-009.
"""

import datetime
import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import (
    DeletionAlreadyPendingError,
    ForbiddenError,
    NotFoundError,
    UnprocessableError,
)
from src.db import get_db
from src.models.classroom_roster import ClassroomRoster
from src.models.deletion_request import DeletionRequest
from src.models.enums import DeletionTargetType
from src.models.learner_profile import LearnerProfile
from src.models.quiz_assignment import QuizAssignment
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.dependencies import current_session_claims
from src.services.auth.tokens import SessionClaims
from src.services.deletion.authorization import can_request_deletion

router = APIRouter()

_TARGET_MODEL: dict[DeletionTargetType, type] = {
    DeletionTargetType.LEARNER: LearnerProfile,
    DeletionTargetType.GUARDIAN: RealGuardianAccount,
    DeletionTargetType.INSTRUCTOR: RealInstructorAccount,
}


class SubmitDeletionRequestIn(BaseModel):
    target_type: DeletionTargetType
    target_id: uuid.UUID
    transfer_rosters_to: uuid.UUID | None = None


class SubmitDeletionRequestOut(BaseModel):
    deletion_request_id: uuid.UUID
    target_type: DeletionTargetType
    target_id: uuid.UUID
    status: Literal["pending"]
    requested_at: datetime.datetime


class DeletionRequestStatusOut(BaseModel):
    deletion_request_id: uuid.UUID
    target_type: DeletionTargetType
    status: Literal["pending", "completed"]
    requested_at: datetime.datetime
    completed_at: datetime.datetime | None


def _transfer_instructor_rosters(
    db: Session, *, instructor_id: uuid.UUID, successor_id: uuid.UUID
) -> None:
    """research.md R5, data-model.md's instructor cascade step 1: moves
    both `classroom_rosters.instructor_id` and `quiz_assignments.
    instructor_id` together, synchronously, so no assignment on a
    transferred roster is left pointing at the instructor about to be
    deleted (`quiz_assignments.instructor_id` is a `NOT NULL` FK)."""
    roster_ids = [
        row[0]
        for row in db.query(ClassroomRoster.roster_id)
        .filter(ClassroomRoster.instructor_id == instructor_id)
        .all()
    ]
    if not roster_ids:
        return
    db.query(ClassroomRoster).filter(ClassroomRoster.roster_id.in_(roster_ids)).update(
        {ClassroomRoster.instructor_id: successor_id}, synchronize_session=False
    )
    db.query(QuizAssignment).filter(QuizAssignment.roster_id.in_(roster_ids)).update(
        {QuizAssignment.instructor_id: successor_id}, synchronize_session=False
    )


@router.post("/api/deletion-requests", response_model=SubmitDeletionRequestOut, status_code=201)
def submit_deletion_request(
    body: SubmitDeletionRequestIn,
    claims: SessionClaims = Depends(current_session_claims),
    db: Session = Depends(get_db),
) -> SubmitDeletionRequestOut:
    target = db.get(_TARGET_MODEL[body.target_type], body.target_id)
    if target is None:
        raise NotFoundError("target_not_found")
    if target.is_demo:
        raise ForbiddenError("not_authorized")
    if not can_request_deletion(claims, body.target_type, body.target_id, db):
        raise ForbiddenError("not_authorized")

    existing_pending = (
        db.query(DeletionRequest)
        .filter(
            DeletionRequest.target_type == body.target_type,
            DeletionRequest.target_id == body.target_id,
            DeletionRequest.completed_at.is_(None),
        )
        .first()
    )
    if existing_pending is not None:
        raise DeletionAlreadyPendingError(existing_pending.deletion_request_id)

    if body.target_type == DeletionTargetType.INSTRUCTOR and body.transfer_rosters_to is not None:
        if body.transfer_rosters_to == body.target_id:
            # A self-transfer is a no-op update (roster still points at
            # the instructor about to be deleted), so the cascade would
            # then find those rosters "never transferred" and hard-
            # delete them -- silently defeating the caller's transfer
            # intent instead of failing loudly.
            raise UnprocessableError("self_transfer_not_allowed")
        successor = db.get(RealInstructorAccount, body.transfer_rosters_to)
        if successor is None or successor.is_demo:
            # classroom_rosters.instructor_id carries no FK (research.md
            # R5), so an unvalidated successor would silently orphan the
            # roster to a dead id instead of failing loudly.
            raise NotFoundError("unknown successor_id")
        _transfer_instructor_rosters(
            db, instructor_id=body.target_id, successor_id=body.transfer_rosters_to
        )

    deletion_request = DeletionRequest(
        target_type=body.target_type,
        target_id=body.target_id,
        requested_by=str(claims.account_id),
    )
    db.add(deletion_request)
    db.commit()
    db.refresh(deletion_request)

    return SubmitDeletionRequestOut(
        deletion_request_id=deletion_request.deletion_request_id,
        target_type=deletion_request.target_type,
        target_id=deletion_request.target_id,
        status="pending",
        requested_at=deletion_request.requested_at,
    )


@router.get("/api/deletion-requests/{deletion_request_id}", response_model=DeletionRequestStatusOut)
def get_deletion_request_status(
    deletion_request_id: uuid.UUID,
    claims: SessionClaims = Depends(current_session_claims),
    db: Session = Depends(get_db),
) -> DeletionRequestStatusOut:
    deletion_request = db.get(DeletionRequest, deletion_request_id)
    if deletion_request is None or deletion_request.requested_by != str(claims.account_id):
        raise ForbiddenError("not_authorized")

    return DeletionRequestStatusOut(
        deletion_request_id=deletion_request.deletion_request_id,
        target_type=deletion_request.target_type,
        status="completed" if deletion_request.completed_at is not None else "pending",
        requested_at=deletion_request.requested_at,
        completed_at=deletion_request.completed_at,
    )
