import enum


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


class ValidationStatus(enum.StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    FLAGGED = "flagged"


class AssessmentEventType(enum.StrEnum):
    PLACEMENT_QUESTION_SHOWN = "placement_question_shown"
    ANSWER_SUBMITTED = "answer_submitted"
    MASTERY_UPDATED = "mastery_updated"
    NEXT_TOPIC_SELECTED = "next_topic_selected"
    QUESTION_FLAGGED = "question_flagged"


def mastery_band_for(p_mastery: float) -> MasteryBand:
    """Derive the three-band mastery classification from a BKT posterior.

    Never cache the result -- data-model.md requires `band` be computed
    at read time from `p_mastery` so the two can never drift apart.
    """
    if p_mastery < 0.4:
        return MasteryBand.STRUGGLING
    if p_mastery < 0.7:
        return MasteryBand.DEVELOPING
    return MasteryBand.MASTERED
