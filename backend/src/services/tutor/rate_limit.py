"""Pre-message rate limit for the Tutor Agent's conversational endpoint
(spec 012 FR-013). Mirrors `services/grading_client/guardrails.py`'s
`check_rate_limit` exactly (research.md §8) -- a DB query counting this
learner's recent submissions in a trailing window, never an in-memory
counter (a fresh Vercel Function invocation has no memory of the last
one).
"""

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession

# Same starting-point constants as spec 007's rate limiter
# (services/grading_client/guardrails.py) -- FR-013 explicitly calls
# for reusing the established pattern, not inventing a new number
# without data behind it (research.md §8).
RATE_LIMIT_MAX_SUBMISSIONS = 20
RATE_LIMIT_WINDOW_MINUTES = 10


@dataclass(frozen=True)
class RateLimitStatus:
    allowed: bool
    retry_after_seconds: int


def check_tutor_rate_limit(db: Session, *, learner_id: uuid.UUID) -> RateLimitStatus:
    """Counts `learner_id`'s `TutorExchange` rows (via their session's
    `learner_id`) in the trailing window -- counted directly off
    `tutor_exchanges.created_at`, not through `assessment_events`
    (research.md §8: no `GeneratedQuestion`-shaped join target exists
    here; `tutor_exchanges` already carries `session_id` ->
    `learner_id`)."""
    now = datetime.datetime.now(datetime.UTC)
    window_start = now - datetime.timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    rows = (
        db.query(TutorExchange.created_at)
        .join(TutoringSession, TutorExchange.session_id == TutoringSession.session_id)
        .filter(
            TutoringSession.learner_id == learner_id,
            TutorExchange.created_at >= window_start,
        )
        .order_by(TutorExchange.created_at.asc())
        .all()
    )
    if len(rows) < RATE_LIMIT_MAX_SUBMISSIONS:
        return RateLimitStatus(allowed=True, retry_after_seconds=0)

    oldest_created_at = rows[0].created_at
    retry_after = (oldest_created_at + datetime.timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)) - now
    return RateLimitStatus(
        allowed=False, retry_after_seconds=max(1, int(retry_after.total_seconds()))
    )
