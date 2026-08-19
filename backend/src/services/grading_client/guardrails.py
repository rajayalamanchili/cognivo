"""Pre-grading guardrails: length cap and rate limit (spec 007 FR-015,
FR-016). Pure precondition checks -- neither writes to the database, both
only read it; the caller (`api/routes/questions.py`) is responsible for
logging a rejection and choosing the HTTP response for a failed check.
"""

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuestionType
from src.models.generated_question import GeneratedQuestion

# Locked per research.md §7.
MAX_ANSWER_LENGTH = 2000
RATE_LIMIT_MAX_SUBMISSIONS = 20
RATE_LIMIT_WINDOW_MINUTES = 10

_COUNTED_EVENT_TYPES = (
    AssessmentEventType.ANSWER_SUBMITTED,
    AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED,
)


def check_length(text: str) -> bool:
    """FR-015: True if `text` is within the locked length cap."""
    return len(text) <= MAX_ANSWER_LENGTH


@dataclass(frozen=True)
class RateLimitStatus:
    allowed: bool
    retry_after_seconds: int


def check_rate_limit(db: Session, *, learner_id: uuid.UUID) -> RateLimitStatus:
    """FR-016: counts this learner's free-text submissions (graded and
    rejected alike) in the trailing window via a DB query, never an
    in-memory counter (research.md §6) -- correct even across separate
    Vercel Function invocations, since each one starts with a fresh
    process."""
    now = datetime.datetime.now(datetime.UTC)
    window_start = now - datetime.timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    rows = (
        db.query(AssessmentEvent.created_at)
        .join(GeneratedQuestion, AssessmentEvent.question_id == GeneratedQuestion.question_id)
        .filter(
            AssessmentEvent.learner_id == learner_id,
            GeneratedQuestion.question_type == QuestionType.FREE_TEXT,
            AssessmentEvent.event_type.in_(_COUNTED_EVENT_TYPES),
            AssessmentEvent.created_at >= window_start,
        )
        .order_by(AssessmentEvent.created_at.asc())
        .all()
    )
    if len(rows) < RATE_LIMIT_MAX_SUBMISSIONS:
        return RateLimitStatus(allowed=True, retry_after_seconds=0)

    oldest_created_at = rows[0].created_at
    retry_after = (oldest_created_at + datetime.timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)) - now
    return RateLimitStatus(
        allowed=False, retry_after_seconds=max(1, int(retry_after.total_seconds()))
    )
