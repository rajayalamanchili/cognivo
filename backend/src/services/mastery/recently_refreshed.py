"""Dashboard "Refreshed!" banner signal (027-learner-ui-redesign,
gap-closing pass -- the mockup's "Order of Operations is back above the
line after yesterday's answer").

Read-only derivation over the existing `mastery_updated` audit log
(Constitution Principle V) -- no new table, no write path. Reads the
`refreshed` flag `mastery_tool.py`'s `refreshed_from_bands` already
computes and `questions.py`/`placement.py` already persist on each
`MASTERY_UPDATED` event (PR #99 review, Principle I: this used to
re-approximate "refreshed" from a raw `p_mastery` threshold, a second,
driftable definition outside the deterministic model -- now it's a
straight read of the one real one).
"""

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, MasteryBand
from src.models.mastery_state import MasteryState

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
    since = datetime.datetime.now(datetime.UTC) - window

    mastered_topic_ids = {
        state.topic_id
        for state in db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .all()
        if state.band is MasteryBand.MASTERED
    }
    if not mastered_topic_ids:
        return None

    # Only the three columns actually used, not full ORM rows -- this is
    # a cosmetic dashboard banner, not worth hydrating learner_id/
    # subject_id/event_id/question_id on every row. Bounded by `since`
    # directly in SQL (an older event outside the window could never be
    # "most recent" anyway), and ordered so the first `refreshed` match
    # is the one to return.
    rows = (
        db.query(AssessmentEvent.topic_id, AssessmentEvent.payload, AssessmentEvent.created_at)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            AssessmentEvent.subject_id == subject_id,
            AssessmentEvent.topic_id.in_(mastered_topic_ids),
            AssessmentEvent.event_type == AssessmentEventType.MASTERY_UPDATED,
            AssessmentEvent.created_at >= since,
        )
        .order_by(AssessmentEvent.created_at.desc())
        .all()
    )
    for topic_id, payload, created_at in rows:
        if (payload or {}).get("refreshed") is True:
            return RecentlyRefreshedTopic(topic_id=topic_id, crossed_at=created_at)

    return None
