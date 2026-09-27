"""Mastery-over-time trend endpoint (spec 025 User Story 5, FR-012)."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db
from src.services.mastery.mastery_history import get_mastery_history

router = APIRouter()


class MasteryHistoryPointOut(BaseModel):
    recorded_at: str
    p_mastery: float


class MasteryHistoryOut(BaseModel):
    points: list[MasteryHistoryPointOut]


@router.get(
    "/api/learners/{learner_id}/topics/{topic_id}/mastery-history",
    response_model=MasteryHistoryOut,
)
def get_mastery_history_route(
    learner_id: uuid.UUID, topic_id: str, subject_id: str, db: Session = Depends(get_db)
) -> MasteryHistoryOut:
    points = get_mastery_history(
        db, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id
    )
    return MasteryHistoryOut(
        points=[
            MasteryHistoryPointOut(
                recorded_at=point.recorded_at.isoformat(), p_mastery=point.p_mastery
            )
            for point in points
        ]
    )
