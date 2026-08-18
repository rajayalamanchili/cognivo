"""Topic-priority-preview endpoint (contracts/api.md, research.md §1/§3)
-- powers the dashboard's path visualization (FR-003/FR-004) by
exposing the Sequencing Agent's existing ranked topic list one layer
further, without generating a question.

Not wrapped in `traced_request()` and writes no `AssessmentEvent` row:
this is an illustrative, non-committing preview, not a real "why was I
shown this" decision (research.md §3) -- matches the existing
`GET /mastery-state`/`GET /recommendations` precedent for untraced
reads.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.sequencing.agent import preview_topic_priority
from src.api.errors import NotFoundError
from src.db import get_db
from src.models.subject import Subject

router = APIRouter()


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


class TopicPreviewEntryOut(BaseModel):
    topic_id: str
    display_name: str
    band: str
    p_mastery: float | None


class TopicPriorityPreviewOut(BaseModel):
    subject_id: str
    next_topic: TopicPreviewEntryOut
    upcoming_topics: list[TopicPreviewEntryOut]
    is_fallback: bool


@router.get(
    "/api/learners/{learner_id}/topic-priority-preview",
    response_model=TopicPriorityPreviewOut,
)
def get_topic_priority_preview(
    learner_id: uuid.UUID, subject_id: str, db: Session = Depends(get_db)
) -> TopicPriorityPreviewOut:
    _get_validated_subject(db, subject_id)

    preview = preview_topic_priority(db, learner_id=learner_id, subject_id=subject_id)

    def to_out(entry) -> TopicPreviewEntryOut:
        return TopicPreviewEntryOut(
            topic_id=entry.topic_id,
            display_name=entry.display_name,
            band=entry.band,
            p_mastery=entry.p_mastery,
        )

    return TopicPriorityPreviewOut(
        subject_id=preview.subject_id,
        next_topic=to_out(preview.next_topic),
        upcoming_topics=[to_out(entry) for entry in preview.upcoming_topics],
        is_fallback=preview.is_fallback,
    )
