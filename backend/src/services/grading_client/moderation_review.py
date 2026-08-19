"""Per-learner moderation-flag escalation check (spec 007 FR-013).

Computed at query time from the `free_text_submission_rejected` events
already written by the guardrail rejection path -- not a persisted
counter column (data-model.md's "derived, not persisted" convention,
matching `models/enums.py::mastery_band_for`'s never-cache rule). No API
endpoint calls this yet in this milestone; a future instructor
review-workflow endpoint (roadmap.md Milestone 7) is the first real
consumer.
"""

import datetime
import uuid

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType

# Locked per research.md §7.
ESCALATION_THRESHOLD = 5
ESCALATION_WINDOW_HOURS = 24


def is_flagged_for_review(db: Session, *, learner_id: uuid.UUID) -> bool:
    """FR-013: True once `learner_id` has crossed the locked
    moderation-flag threshold within the rolling window. Only
    `reason: "moderation"` rejections count -- `"too_long"` and
    `"rate_limited"` rejections never escalate (data-model.md)."""
    window_start = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        hours=ESCALATION_WINDOW_HOURS
    )
    rows = (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.event_type == AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED,
            AssessmentEvent.created_at >= window_start,
        )
        .all()
    )
    moderation_count = sum(1 for row in rows if row.payload.get("reason") == "moderation")
    return moderation_count >= ESCALATION_THRESHOLD
