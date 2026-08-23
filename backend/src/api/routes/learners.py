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
