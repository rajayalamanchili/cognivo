"""Mastery-state endpoint (contracts/api.md) -- backs the "why was I
placed here" mastery view (Constitution Principle V)."""

import datetime
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import NotFoundError
from src.db import get_db
from src.models.mastery_state import MasteryState
from src.models.subject import Subject
from src.models.topic import Topic
from src.services.mastery.decay import effective_mastery_for_review
from src.services.mediation.grade import resolve_unlocked_grade

router = APIRouter()


class MasteryTopicOut(BaseModel):
    topic_id: str
    status: str
    p_mastery: float | None = None
    band: str | None = None
    last_updated_at: str | None = None
    # Spec 025 FR-005/FR-006: decay-adjusted mastery, reusing decay.py's
    # own pure function -- `p_mastery` above is unchanged and now doubles
    # as "peak" mastery in the dashboard's framing.
    effective_p_mastery: float | None = None


class MasteryStateResponse(BaseModel):
    topics: list[MasteryTopicOut]
    # Spec 025 FR-016: lets the frontend route explanation copy through
    # the same age-adaptive tier as the rest of the explainability UI
    # (`getExplanationCopyTier`) instead of always falling back to the
    # ungraded/default tier.
    unlocked_grade: int | None = None


@router.get("/api/learners/{learner_id}/mastery-state", response_model=MasteryStateResponse)
def get_mastery_state(
    learner_id: uuid.UUID, subject_id: str, db: Session = Depends(get_db)
) -> MasteryStateResponse:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise NotFoundError(f"unknown subject_id: {subject_id!r}")

    topics = (
        db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.order_index).all()
    )
    states = {
        state.topic_id: state
        for state in db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .all()
    }

    now = datetime.datetime.now(datetime.UTC)
    topics_out: list[MasteryTopicOut] = []
    for topic in topics:
        state = states.get(topic.topic_id)
        if state is None:
            topics_out.append(MasteryTopicOut(topic_id=topic.topic_id, status="unknown"))
        else:
            topics_out.append(
                MasteryTopicOut(
                    topic_id=topic.topic_id,
                    status="scored",
                    p_mastery=state.p_mastery,
                    band=state.band.value,
                    last_updated_at=state.updated_at.isoformat(),
                    effective_p_mastery=effective_mastery_for_review(
                        state.p_mastery, updated_at=state.updated_at, now=now
                    ),
                )
            )

    return MasteryStateResponse(
        topics=topics_out,
        unlocked_grade=resolve_unlocked_grade(db, learner_id=learner_id, subject_id=subject_id),
    )
