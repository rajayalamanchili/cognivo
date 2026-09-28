"""Mastery-over-time trend query (spec 025 User Story 5, FR-012).

Read-only, no new table -- `AssessmentEvent`'s already-durable
`mastery_updated` audit trail (Constitution Principle V) is the data
source, mirroring `weak_area.py`'s `_build_evidence` query pattern.
"""

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType


@dataclass(frozen=True)
class MasteryHistoryPoint:
    recorded_at: datetime.datetime
    p_mastery: float


def get_mastery_history(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, topic_id: str
) -> list[MasteryHistoryPoint]:
    """Every `mastery_updated` event for this topic, chronologically --
    empty for a topic with no `MasteryState` at all (FR-012's "unknown"
    edge case), never a 404."""
    events = (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.subject_id == subject_id,
            AssessmentEvent.topic_id == topic_id,
            AssessmentEvent.event_type == AssessmentEventType.MASTERY_UPDATED,
        )
        .order_by(AssessmentEvent.created_at)
        .all()
    )
    return [
        MasteryHistoryPoint(
            recorded_at=event.created_at, p_mastery=event.payload["posterior_p_mastery"]
        )
        for event in events
    ]
