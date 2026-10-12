"""Guardian-authenticated learner-profile creation (contracts/api.md
"Auth" section). Creates the `LearnerProfile` and its `RetentionRecord`
in the same transaction -- spec 009 SC-004: no account can be created
without one.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enums import AuthorizedByType, RetentionAccountType, RetentionEnrollmentStatus
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.retention_record import RetentionRecord
from src.services.auth.dependencies import current_guardian

router = APIRouter()


class CreateLearnerIn(BaseModel):
    display_name: str


class CreateLearnerOut(BaseModel):
    learner_id: uuid.UUID
    guardian_id: uuid.UUID


@router.post("/api/learners", response_model=CreateLearnerOut, status_code=201)
def create_learner(
    body: CreateLearnerIn,
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> CreateLearnerOut:
    learner_id = uuid.uuid4()

    retention_record = RetentionRecord(
        account_type=RetentionAccountType.LEARNER,
        account_id=learner_id,
        authorized_by_type=AuthorizedByType.GUARDIAN,
        authorized_by_id=guardian.guardian_id,
        enrollment_status=RetentionEnrollmentStatus.ACTIVE,
    )
    db.add(retention_record)
    db.flush()

    learner = LearnerProfile(
        learner_id=learner_id,
        display_name=body.display_name,
        is_demo=False,
        guardian_id=guardian.guardian_id,
        retention_record_id=retention_record.retention_record_id,
    )
    db.add(learner)
    db.commit()

    return CreateLearnerOut(learner_id=learner_id, guardian_id=guardian.guardian_id)


class MyLearnerEnrollmentOut(BaseModel):
    roster_id: uuid.UUID
    subject_id: str
    grade: int | None


class MyLearnerOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    enrollments: list[MyLearnerEnrollmentOut]


class ListMyLearnersOut(BaseModel):
    learners: list[MyLearnerOut]


@router.get("/api/learners/mine", response_model=ListMyLearnersOut)
def list_my_learners_route(
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> ListMyLearnersOut:
    """FR-001/FR-023 (spec 044/041): Guardian · My learners, Settings'
    Learners section, and the class directory's learner picker all need
    the guardian's persisted learner set, not just whatever
    `addedLearners` session-local state happened to add this browser
    session. Same ownership scoping and `Enrollment`-joined-to-
    `ClassroomRoster` pattern `list_learner_enrollments_route` already
    uses, just rooted at the guardian instead of a single `learner_id`.
    Returns every roster a learner is enrolled in (spec 044 FR-001) --
    previously collapsed to just the first one the query happened to
    return.
    """
    learners = (
        db.query(LearnerProfile).filter(LearnerProfile.guardian_id == guardian.guardian_id).all()
    )
    rosters_by_learner_id: dict[uuid.UUID, list[ClassroomRoster]] = {}
    if learners:
        rows = (
            db.query(Enrollment.learner_id, ClassroomRoster)
            .join(ClassroomRoster, ClassroomRoster.roster_id == Enrollment.roster_id)
            .filter(Enrollment.learner_id.in_([learner.learner_id for learner in learners]))
            .all()
        )
        for learner_id, roster in rows:
            rosters_by_learner_id.setdefault(learner_id, []).append(roster)

    return ListMyLearnersOut(
        learners=[
            MyLearnerOut(
                learner_id=learner.learner_id,
                display_name=learner.display_name,
                enrollments=[
                    MyLearnerEnrollmentOut(
                        roster_id=roster.roster_id,
                        subject_id=roster.subject_id,
                        grade=roster.grade,
                    )
                    for roster in rosters_by_learner_id.get(learner.learner_id, [])
                ],
            )
            for learner in learners
        ]
    )
