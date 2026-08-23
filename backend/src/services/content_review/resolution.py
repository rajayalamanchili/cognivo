"""Content-review queue scoping and resolution (FR-011/FR-012/FR-013,
research.md §5).

The flagged-question queue is computed by joining `GeneratedQuestion`
(filtered to `validation_status: flagged`) through `Enrollment` to the
requesting instructor's `ClassroomRoster` rows at query time --
`GeneratedQuestion` itself gains no new instructor-facing column
(research.md §5): a learner's roster membership can change after a
question was flagged, so a denormalized instructor_id snapshot would
go stale the moment that changes. The join additionally requires the
roster's `subject_id` match the question's -- a learner may be
enrolled in this instructor's rosters across more than one subject
(FR-007), and only the roster matching the flagged question's own
subject is the relevant one to attribute it to.
"""

import datetime
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from src.api.errors import ForbiddenError, NotFoundError
from src.models.assessment_event import AssessmentEvent
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enums import AssessmentEventType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.services.audit_log.writer import record_event

ResolutionAction = Literal["reactivate", "reject"]


@dataclass(frozen=True)
class FlaggedQuestionEntry:
    question_id: uuid.UUID
    learner_id: uuid.UUID
    roster_id: uuid.UUID
    stem: str
    flagged_reason: str | None
    flagged_at: datetime.datetime


def _latest_flagged_at(db: Session, question_id: uuid.UUID) -> datetime.datetime:
    """A `FLAGGED` question always has at least one `QUESTION_FLAGGED`
    event -- the only write path setting `validation_status: flagged`
    (`questions.py`'s `flag_question`) always records one in the same
    transaction. The most recent one covers a question re-flagged after
    a prior reactivate."""
    event = (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question_id,
            AssessmentEvent.event_type == AssessmentEventType.QUESTION_FLAGGED,
        )
        .order_by(AssessmentEvent.created_at.desc())
        .first()
    )
    assert event is not None, f"flagged question {question_id} has no QUESTION_FLAGGED event"
    return event.created_at


def list_flagged_questions(db: Session, *, instructor_id: uuid.UUID) -> list[FlaggedQuestionEntry]:
    rows = (
        db.query(GeneratedQuestion, ClassroomRoster)
        .join(Enrollment, Enrollment.learner_id == GeneratedQuestion.learner_id)
        .join(ClassroomRoster, ClassroomRoster.roster_id == Enrollment.roster_id)
        .filter(
            GeneratedQuestion.validation_status == ValidationStatus.FLAGGED,
            ClassroomRoster.instructor_id == instructor_id,
            ClassroomRoster.subject_id == GeneratedQuestion.subject_id,
        )
        .order_by(GeneratedQuestion.generated_at)
        .all()
    )
    return [
        FlaggedQuestionEntry(
            question_id=question.question_id,
            learner_id=question.learner_id,
            roster_id=roster.roster_id,
            stem=question.stem,
            flagged_reason=question.flagged_reason,
            flagged_at=_latest_flagged_at(db, question.question_id),
        )
        for question, roster in rows
    ]


def _question_belongs_to_instructor(
    db: Session, *, question: GeneratedQuestion, instructor_id: uuid.UUID
) -> bool:
    return (
        db.query(ClassroomRoster)
        .join(Enrollment, Enrollment.roster_id == ClassroomRoster.roster_id)
        .filter(
            Enrollment.learner_id == question.learner_id,
            ClassroomRoster.instructor_id == instructor_id,
            ClassroomRoster.subject_id == question.subject_id,
        )
        .first()
        is not None
    )


def resolve_flagged_question(
    db: Session, *, question_id: uuid.UUID, instructor_id: uuid.UUID, action: ResolutionAction
) -> GeneratedQuestion:
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise NotFoundError("unknown question_id")
    if not _question_belongs_to_instructor(db, question=question, instructor_id=instructor_id):
        raise ForbiddenError("not_learner_on_your_roster")

    if action == "reactivate":
        question.validation_status = ValidationStatus.VALID
    # "reject": stays FLAGGED permanently -- data-model.md's
    # GeneratedQuestion.validation_status state transitions: no further
    # state beyond flagged/valid.

    record_event(
        db,
        learner_id=question.learner_id,
        event_type=AssessmentEventType.CONTENT_REVIEW_RESOLVED,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        question_id=question.question_id,
        payload={"action": action, "resolved_by_instructor_id": str(instructor_id)},
    )
    db.commit()
    return question
