"""Roster CRUD, join, approve/decline, and unenroll (contracts/api.md
"Rosters" section, User Story 2).
"""

import datetime
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.errors import ForbiddenError, NotFoundError
from src.db import get_db
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enrollment_request import EnrollmentRequest
from src.models.enums import EnrollmentMode
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.models.subject import Subject
from src.services.auth.dependencies import (
    InstructorAccount,
    current_guardian,
    current_instructor,
    current_session_claims,
)
from src.services.auth.tokens import SessionClaims
from src.services.roster.enrollment import (
    approve_request,
    create_roster,
    decline_request,
    join_roster,
    unenroll,
    update_roster,
)

router = APIRouter()


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


def _get_owned_roster(
    db: Session, roster_id: uuid.UUID, instructor: InstructorAccount
) -> ClassroomRoster:
    roster = db.get(ClassroomRoster, roster_id)
    if roster is None:
        raise NotFoundError("unknown roster_id")
    if roster.instructor_id != instructor.instructor_id:
        raise ForbiddenError("not_roster_owner")
    return roster


class RosterOut(BaseModel):
    roster_id: uuid.UUID
    subject_id: str
    enrollment_mode: str
    join_code: str | None
    grade: int | None
    is_listed: bool


class RosterSummaryOut(BaseModel):
    roster_id: uuid.UUID
    subject_id: str
    enrollment_mode: str
    grade: int | None
    is_listed: bool


class ListRostersOut(BaseModel):
    rosters: list[RosterSummaryOut]


def _roster_out(roster: ClassroomRoster) -> RosterOut:
    # A closed roster's join_code is never null in the DB (it's the
    # only field POST /api/rosters/join uses to find the roster --
    # data-model.md's Correction) and is always returned here too (PR
    # #28 review, second Correction): every caller of this function is
    # already the roster's owner (create_roster_route just created it;
    # update_roster_route is gated by _get_owned_roster), so there's no
    # one else this could leak to -- and nulling it unconditionally, as
    # the original contract said, left the owning instructor with no
    # way to ever learn a closed roster's own code, making closed-roster
    # enrollment (FR-006) unreachable through the product entirely.
    return RosterOut(
        roster_id=roster.roster_id,
        subject_id=roster.subject_id,
        enrollment_mode=roster.enrollment_mode.value,
        join_code=roster.join_code,
        grade=roster.grade,
        is_listed=roster.is_listed,
    )


class RosterDirectoryEntryOut(BaseModel):
    roster_id: uuid.UUID
    subject_id: str
    grade: int | None
    instructor_display_name: str
    join_code: str


class RosterDirectoryOut(BaseModel):
    rosters: list[RosterDirectoryEntryOut]


@router.get("/api/rosters/directory", response_model=RosterDirectoryOut)
def roster_directory_route(
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> RosterDirectoryOut:
    """spec 041 FR-019/FR-021. `join_code` is no longer secret once
    `is_listed=True` -- the instructor's own explicit choice
    (research.md §3) -- so it's included directly, letting the
    frontend's "join from directory" action reuse the existing
    `POST /api/rosters/join` with no second enrollment path.
    `instructor_id` is not a FK (see `ClassroomRoster`'s own docstring),
    so this join is explicit rather than an ORM relationship; it also
    naturally excludes a roster owned by a demo instructor, since no
    `RealInstructorAccount` row ever shares a demo instructor's id."""
    rows = (
        db.query(ClassroomRoster, RealInstructorAccount)
        .join(
            RealInstructorAccount,
            RealInstructorAccount.instructor_id == ClassroomRoster.instructor_id,
        )
        .filter(
            ClassroomRoster.is_listed.is_(True),
            ClassroomRoster.enrollment_mode == EnrollmentMode.OPEN,
        )
        .all()
    )
    return RosterDirectoryOut(
        rosters=[
            RosterDirectoryEntryOut(
                roster_id=roster.roster_id,
                subject_id=roster.subject_id,
                grade=roster.grade,
                instructor_display_name=instructor.display_name,
                join_code=roster.join_code,
            )
            for roster, instructor in rows
        ]
    )


class CreateRosterIn(BaseModel):
    subject_id: str
    enrollment_mode: EnrollmentMode
    grade: int | None = Field(default=None, ge=1, le=12)


@router.post("/api/rosters", response_model=RosterOut, status_code=201)
def create_roster_route(
    body: CreateRosterIn,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> RosterOut:
    _get_validated_subject(db, body.subject_id)
    roster = create_roster(
        db,
        instructor_id=instructor.instructor_id,
        subject_id=body.subject_id,
        enrollment_mode=body.enrollment_mode,
        grade=body.grade,
    )
    return _roster_out(roster)


class UpdateRosterIn(BaseModel):
    enrollment_mode: EnrollmentMode
    # spec 041 FR-017/FR-018: optional, alongside the existing
    # enrollment_mode -- `None` leaves is_listed untouched.
    is_listed: bool | None = None


@router.patch("/api/rosters/{roster_id}", response_model=RosterOut)
def update_roster_route(
    roster_id: uuid.UUID,
    body: UpdateRosterIn,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> RosterOut:
    roster = _get_owned_roster(db, roster_id, instructor)
    roster = update_roster(
        db,
        roster=roster,
        enrollment_mode=body.enrollment_mode,
        is_listed=body.is_listed,
        instructor_display_name=getattr(instructor, "display_name", None),
    )
    return _roster_out(roster)


@router.get("/api/rosters", response_model=ListRostersOut)
def list_rosters_route(
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> ListRostersOut:
    rosters = (
        db.query(ClassroomRoster)
        .filter(ClassroomRoster.instructor_id == instructor.instructor_id)
        .order_by(ClassroomRoster.created_at)
        .all()
    )
    return ListRostersOut(
        rosters=[
            RosterSummaryOut(
                roster_id=roster.roster_id,
                subject_id=roster.subject_id,
                enrollment_mode=roster.enrollment_mode.value,
                grade=roster.grade,
                is_listed=roster.is_listed,
            )
            for roster in rosters
        ]
    )


class JoinRosterIn(BaseModel):
    learner_id: uuid.UUID
    join_code: str


@router.post("/api/rosters/join")
def join_roster_route(
    body: JoinRosterIn,
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> JSONResponse:
    learner = db.get(LearnerProfile, body.learner_id)
    if learner is None or learner.guardian_id != guardian.guardian_id:
        raise ForbiddenError("not_your_learner")

    outcome, obj = join_roster(
        db, learner_id=body.learner_id, guardian_id=guardian.guardian_id, join_code=body.join_code
    )
    if outcome == "enrolled":
        return JSONResponse(
            status_code=201, content={"status": "enrolled", "enrollment_id": str(obj.enrollment_id)}
        )
    return JSONResponse(
        status_code=202,
        content={"status": "pending", "enrollment_request_id": str(obj.enrollment_request_id)},
    )


class RequestOut(BaseModel):
    enrollment_request_id: uuid.UUID
    learner_id: uuid.UUID
    requested_at: datetime.datetime


class ListRequestsOut(BaseModel):
    requests: list[RequestOut]


@router.get("/api/rosters/{roster_id}/requests", response_model=ListRequestsOut)
def list_requests_route(
    roster_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> ListRequestsOut:
    _get_owned_roster(db, roster_id, instructor)
    requests = (
        db.query(EnrollmentRequest)
        .filter(EnrollmentRequest.roster_id == roster_id, EnrollmentRequest.decision.is_(None))
        .order_by(EnrollmentRequest.requested_at)
        .all()
    )
    return ListRequestsOut(
        requests=[
            RequestOut(
                enrollment_request_id=request.enrollment_request_id,
                learner_id=request.learner_id,
                requested_at=request.requested_at,
            )
            for request in requests
        ]
    )


class EnrolledLearnerOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str


class ListEnrollmentsOut(BaseModel):
    enrollments: list[EnrolledLearnerOut]


@router.get("/api/rosters/{roster_id}/enrollments", response_model=ListEnrollmentsOut)
def list_enrollments_route(
    roster_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> ListEnrollmentsOut:
    """Not in the original contracts/api.md -- added while building
    T035's roster-management page (`/speckit-clarify` with the user):
    that page needs to list a roster's currently-enrolled learners with
    an unenroll action, and no Phase 4 endpoint returned that (only
    Phase 5's dashboard endpoint, `GET /api/rosters/{roster_id}/dashboard`,
    includes learner identity -- alongside a full weak-area report this
    endpoint deliberately doesn't compute)."""
    _get_owned_roster(db, roster_id, instructor)
    rows = (
        db.query(LearnerProfile)
        .join(Enrollment, Enrollment.learner_id == LearnerProfile.learner_id)
        .filter(Enrollment.roster_id == roster_id)
        .order_by(LearnerProfile.display_name)
        .all()
    )
    return ListEnrollmentsOut(
        enrollments=[
            EnrolledLearnerOut(learner_id=learner.learner_id, display_name=learner.display_name)
            for learner in rows
        ]
    )


class LearnerEnrollmentOut(BaseModel):
    roster_id: uuid.UUID
    subject_id: str


class ListLearnerEnrollmentsOut(BaseModel):
    enrollments: list[LearnerEnrollmentOut]


@router.get("/api/learners/{learner_id}/enrollments", response_model=ListLearnerEnrollmentsOut)
def list_learner_enrollments_route(
    learner_id: uuid.UUID,
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> ListLearnerEnrollmentsOut:
    """Not in spec 038's original contracts/api-changes.md -- added
    while wiring the guardian's own learner-progress page (T014): no
    existing endpoint told the guardian frontend which subject(s) a
    learner is enrolled in, which `GET /mastery-state` needs as a query
    param. Same shape/ownership-check pattern as `list_enrollments_route`
    above, scoped by learner instead of by roster."""
    learner = db.get(LearnerProfile, learner_id)
    if learner is None or learner.guardian_id != guardian.guardian_id:
        raise ForbiddenError("not_your_learner")
    rows = (
        db.query(ClassroomRoster)
        .join(Enrollment, Enrollment.roster_id == ClassroomRoster.roster_id)
        .filter(Enrollment.learner_id == learner_id)
        .all()
    )
    return ListLearnerEnrollmentsOut(
        enrollments=[
            LearnerEnrollmentOut(roster_id=roster.roster_id, subject_id=roster.subject_id)
            for roster in rows
        ]
    )


def _get_owned_pending_request(
    db: Session,
    roster_id: uuid.UUID,
    enrollment_request_id: uuid.UUID,
    instructor: InstructorAccount,
) -> EnrollmentRequest:
    _get_owned_roster(db, roster_id, instructor)
    request = db.get(EnrollmentRequest, enrollment_request_id)
    if request is None or request.roster_id != roster_id:
        raise NotFoundError("unknown enrollment_request_id")
    return request


@router.post("/api/rosters/{roster_id}/requests/{enrollment_request_id}/approve")
def approve_request_route(
    roster_id: uuid.UUID,
    enrollment_request_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> JSONResponse:
    request = _get_owned_pending_request(db, roster_id, enrollment_request_id, instructor)
    enrollment = approve_request(db, request=request, instructor_id=instructor.instructor_id)
    return JSONResponse(
        status_code=200,
        content={"status": "approved", "enrollment_id": str(enrollment.enrollment_id)},
    )


@router.post("/api/rosters/{roster_id}/requests/{enrollment_request_id}/decline")
def decline_request_route(
    roster_id: uuid.UUID,
    enrollment_request_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> JSONResponse:
    request = _get_owned_pending_request(db, roster_id, enrollment_request_id, instructor)
    decline_request(db, request=request)
    return JSONResponse(status_code=200, content={"status": "declined"})


@router.delete("/api/rosters/{roster_id}/enrollments/{learner_id}", status_code=204)
def delete_enrollment_route(
    roster_id: uuid.UUID,
    learner_id: uuid.UUID,
    claims: SessionClaims = Depends(current_session_claims),
    db: Session = Depends(get_db),
) -> None:
    roster = db.get(ClassroomRoster, roster_id)
    if roster is None:
        raise NotFoundError("unknown roster_id")

    if claims.account_type in ("instructor", "demo_instructor"):
        if roster.instructor_id != claims.account_id:
            raise ForbiddenError("not_roster_owner")
    else:
        learner = db.get(LearnerProfile, learner_id)
        if learner is None or learner.guardian_id != claims.account_id:
            raise ForbiddenError("not_learner_guardian")

    unenroll(db, roster_id=roster_id, learner_id=learner_id)
