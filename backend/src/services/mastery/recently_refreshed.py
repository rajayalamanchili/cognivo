"""Dashboard "Refreshed!" banner signal (027-learner-ui-redesign,
gap-closing pass -- the mockup's "Order of Operations is back above the
line after yesterday's answer").

Read-only derivation over the existing `mastery_updated` audit log
(Constitution Principle V) -- no new table, no write path. Mirrors
`mastery_tool.py`'s own `refreshed_from_bands` definition of "refreshed"
(crossed from below the mastered band to above it, having reached
mastered at some *earlier* point too -- never a topic's first-ever
mastery) as closely as the audit log allows: `MASTERY_UPDATED` events
don't persist `consecutive_mastered_observations`, so this can't replay
`mastery_band_for`'s confirmation-streak gate exactly. It approximates
with the raw 0.7 `p_mastery` threshold instead, guarded by requiring a
*prior* event that also reached that threshold -- the same guard
`refreshed_from_bands` uses to rule out first-time mastery, just
checked across the audit trail instead of one sticky column.
"""

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, MasteryBand
from src.models.mastery_state import MasteryState

# Same raw-score cutoff `mastery_band_for` (models/enums.py) uses for
# "mastered" -- duplicated here (not imported) because the confirmation
# streak that function also requires isn't recoverable from the audit
# log, so this is deliberately an approximation of that rule, not a
# call to it.
MASTERED_THRESHOLD = 0.7

TRAILING_WINDOW = datetime.timedelta(days=7)


@dataclass(frozen=True)
class RecentlyRefreshedTopic:
    topic_id: str
    crossed_at: datetime.datetime


def find_recently_refreshed_topic(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    window: datetime.timedelta = TRAILING_WINDOW,
) -> RecentlyRefreshedTopic | None:
    """The most recently "refreshed" topic in `subject_id` for
    `learner_id`, or `None`. Only considers topics whose *current* band
    is mastered -- a topic that crossed back above the line and then
    decayed or regressed again since isn't still showing as refreshed.
    """
    now = datetime.datetime.now(datetime.UTC)
    since = now - window

    mastered_topic_ids = {
        state.topic_id
        for state in db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .all()
        if state.band is MasteryBand.MASTERED
    }
    if not mastered_topic_ids:
        return None

    best: RecentlyRefreshedTopic | None = None
    for topic_id in mastered_topic_ids:
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
        reached_mastered_before = False
        for event in events:
            prior = event.payload.get("prior_p_mastery")
            posterior = event.payload["posterior_p_mastery"]
            crossed_now = prior is not None and prior < MASTERED_THRESHOLD <= posterior
            if (
                crossed_now
                and reached_mastered_before
                and event.created_at >= since
                and (best is None or event.created_at > best.crossed_at)
            ):
                best = RecentlyRefreshedTopic(topic_id=topic_id, crossed_at=event.created_at)
            if posterior >= MASTERED_THRESHOLD:
                reached_mastered_before = True

    return best
