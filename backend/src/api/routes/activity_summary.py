"""Dashboard activity-summary endpoint (027-learner-ui-redesign FR-009) --
backs the "questions this week" stat tile. The sole new backend surface
this feature introduces: no existing endpoint or already-fetched
response exposes a weekly answer count, so this is a narrow, read-only
aggregate query over the existing `AssessmentEvent` audit log
(Constitution Principle V) -- no new table, no write path.
"""

import datetime
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.errors import NotFoundError
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.subject import Subject
from src.services.auth.dependencies import (
    optional_session_claims,
    require_learner_ownership_if_real,
)
from src.services.auth.tokens import SessionClaims

router = APIRouter()

TRAILING_WINDOW = datetime.timedelta(days=7)


class ActivitySummaryResponse(BaseModel):
    questions_this_week: int


@router.get(
    "/api/learners/{learner_id}/activity-summary",
    response_model=ActivitySummaryResponse,
)
def get_activity_summary(
    learner_id: uuid.UUID,
    subject_id: str,
    db: Session = Depends(get_db),
    claims: SessionClaims | None = Depends(optional_session_claims),
) -> ActivitySummaryResponse:
    require_learner_ownership_if_real(db, learner_id=learner_id, claims=claims)
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError(f"unknown subject_id: {subject_id!r}")

    since = datetime.datetime.now(datetime.UTC) - TRAILING_WINDOW
    count = (
        db.query(func.count(AssessmentEvent.event_id))
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.subject_id == subject_id,
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            AssessmentEvent.created_at >= since,
        )
        .scalar()
    )

    return ActivitySummaryResponse(questions_this_week=count or 0)
