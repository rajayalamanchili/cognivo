"""AssessmentEvent audit-log writer (FR-010, SC-006).

Every sequencing decision, generated question, and grading outcome MUST
be logged with enough context to answer "why was I shown this" / "why
was this marked wrong" after the fact (Constitution Principle V). This
is the single write path for `AssessmentEvent` rows -- agents and API
routes call `record_event` rather than constructing rows themselves, so
the shape of `payload` per `event_type` stays consistent.
"""

import uuid

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType


def record_event(
    db: Session,
    *,
    learner_id: uuid.UUID,
    event_type: AssessmentEventType,
    subject_id: str,
    topic_id: str | None,
    payload: dict,
    question_id: uuid.UUID | None = None,
) -> AssessmentEvent:
    """Append one AssessmentEvent row. Does not commit -- callers control
    the transaction boundary so this can be written atomically alongside
    the mastery/question state change it documents.

    `topic_id` is nullable for spec 002's `recommendation_report_generated`
    event, which summarizes a whole report rather than a single topic
    -- every other event type still always passes a real `topic_id`.
    """
    event = AssessmentEvent(
        learner_id=learner_id,
        event_type=event_type,
        question_id=question_id,
        subject_id=subject_id,
        topic_id=topic_id,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event
