import enum
from collections.abc import Sequence


def enum_values(enum_cls: type[enum.Enum]) -> Sequence[str]:
    """`values_callable` for every `sqlalchemy.Enum(...)` column below.

    Without this, SQLAlchemy binds/creates the Postgres enum type using
    each member's `.name` (e.g. "EASY") instead of `.value` ("easy") --
    the Alembic migration's `CREATE TYPE` already uses the lowercase
    `.value` strings, so leaving this out desyncs runtime inserts from
    the actual DB enum labels.
    """
    return [member.value for member in enum_cls]


class DifficultyBand(enum.StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class MasteryBand(enum.StrEnum):
    STRUGGLING = "struggling"
    DEVELOPING = "developing"
    MASTERED = "mastered"


class QuestionType(enum.StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    NUMERIC = "numeric"
    FREE_TEXT = "free_text"


class ValidationStatus(enum.StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    FLAGGED = "flagged"


class QuizSessionStatus(enum.StrEnum):
    """spec 005 data-model.md: an abandoned quiz is simply one left
    IN_PROGRESS forever -- there is no distinct "abandoned" member."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ENDED_EARLY = "ended_early"


class EnrollmentMode(enum.StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class AuthorizedByType(enum.StrEnum):
    GUARDIAN = "guardian"
    INSTRUCTOR = "instructor"


class EnrollmentDecision(enum.StrEnum):
    APPROVED = "approved"
    DECLINED = "declined"


class DeletionTargetType(enum.StrEnum):
    LEARNER = "learner"
    INSTRUCTOR = "instructor"
    GUARDIAN = "guardian"


class RetentionAccountType(enum.StrEnum):
    LEARNER = "learner"
    INSTRUCTOR = "instructor"


class RetentionEnrollmentStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AssessmentEventType(enum.StrEnum):
    PLACEMENT_QUESTION_SHOWN = "placement_question_shown"
    ANSWER_SUBMITTED = "answer_submitted"
    MASTERY_UPDATED = "mastery_updated"
    NEXT_TOPIC_SELECTED = "next_topic_selected"
    QUESTION_FLAGGED = "question_flagged"
    RECOMMENDATION_REPORT_GENERATED = "recommendation_report_generated"
    WEAK_AREA_FLAGGED = "weak_area_flagged"
    NEXT_STEP_SUGGESTED = "next_step_suggested"
    QUIZ_DIFFICULTY_ADJUSTED = "quiz_difficulty_adjusted"
    FREE_TEXT_SUBMISSION_REJECTED = "free_text_submission_rejected"
    CONTENT_REVIEW_RESOLVED = "content_review_resolved"
    QUIZ_ASSIGNMENT_CREATED = "quiz_assignment_created"
    QUIZ_ASSIGNMENT_CANCELLED = "quiz_assignment_cancelled"


# Consecutive post-update observations with p_mastery >= 0.7 required
# before "mastered" is actually reported (data-model.md's Mastered-
# confirmation rule). A single numeric-question correct answer is, on
# its own, strong enough Bayesian evidence (p(G)=0.05) to cross 0.7 from
# one lucky guess -- without this gate, a degenerate content-blind
# answer pattern could spike a topic into "mastered" off one coincidence
# and then never be re-practiced (FR-006 removes mastered topics from
# selection), permanently locking in a false signal. This directly
# implements SC-005: two consecutive high-confidence observations are
# required, not just one.
MASTERY_CONFIRMATION_THRESHOLD = 2


def mastery_band_for(p_mastery: float, consecutive_mastered_observations: int) -> MasteryBand:
    """Derive the three-band mastery classification from a BKT posterior.

    Never cache the result -- data-model.md requires `band` be computed
    at read time from `p_mastery` (plus the persisted confirmation
    streak below) so the two can never drift apart.

    `consecutive_mastered_observations` is the number of consecutive
    prior updates (including this one) where the posterior was already
    >= 0.7 -- see `MASTERY_CONFIRMATION_THRESHOLD`. A posterior >= 0.7
    that hasn't yet been confirmed reports as "developing", not
    "mastered".
    """
    if p_mastery < 0.4:
        return MasteryBand.STRUGGLING
    if p_mastery < 0.7:
        return MasteryBand.DEVELOPING
    if consecutive_mastered_observations >= MASTERY_CONFIRMATION_THRESHOLD:
        return MasteryBand.MASTERED
    return MasteryBand.DEVELOPING
