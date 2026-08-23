"""Assignment creation, cancellation, and target-list resolution (spec
011 FR-001-FR-005, FR-012, FR-015; research.md §1/§4/§6/§7).

`create_assignment`/`cancel_assignment` never touch `QuizSession`,
`GeneratedQuestion`, or the grading/mastery-update path -- an
assignment attempt is just an ordinary `QuizSession` (research.md §1),
started via `services/quiz/session.py`'s existing `start_quiz()`
(User Story 2's `start_assignment_attempt()`, not this module).
"""

import datetime
import uuid
from collections.abc import Sequence
from typing import Literal

from sqlalchemy.orm import Session

from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.models.assessment_event import AssessmentEvent
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.models.quiz_session import QuizSession
from src.models.topic import Topic
from src.services.audit_log.writer import record_event

LearnerIdsIn = list[uuid.UUID] | Literal["all"]


def resolve_target_learner_ids(
    learner_ids: LearnerIdsIn, *, enrolled_learner_ids: Sequence[uuid.UUID]
) -> list[uuid.UUID]:
    """Resolves the requested `learner_ids` against the roster's
    currently-enrolled learners (FR-002) -- a subset entry that isn't
    (or is no longer) enrolled is silently dropped, exactly as `"all"`
    only ever resolves to learners actually enrolled right now
    (research.md §4). Raises `UnprocessableError` if the resulting list
    is empty (FR-003)."""
    if learner_ids == "all":
        resolved = list(enrolled_learner_ids)
    else:
        enrolled_set = set(enrolled_learner_ids)
        resolved = []
        seen: set[uuid.UUID] = set()
        for learner_id in learner_ids:
            if learner_id in enrolled_set and learner_id not in seen:
                resolved.append(learner_id)
                seen.add(learner_id)

    if not resolved:
        raise UnprocessableError("empty_target")
    return resolved


def _resolve_assignment_subject_id(
    db: Session, *, topic_ids: list[str], roster_subject_id: str
) -> str:
    """Mirrors `quiz.py`'s `_resolve_quiz_subject_id`, plus the extra
    constraint (data-model.md) that every topic must belong to the
    roster's own subject -- an assignment can't target a different
    subject than the roster it's scoped to."""
    for topic_id in topic_ids:
        topic = (
            db.query(Topic)
            .filter(Topic.topic_id == topic_id, Topic.subject_id == roster_subject_id)
            .first()
        )
        if topic is None:
            raise NotFoundError(f"unknown or cross-subject topic_id: {topic_id!r}")
    return roster_subject_id


def _enrolled_learner_ids(db: Session, *, roster_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        row[0]
        for row in db.query(Enrollment.learner_id).filter(Enrollment.roster_id == roster_id).all()
    ]


def create_assignment(
    db: Session,
    *,
    roster: ClassroomRoster,
    instructor_id: uuid.UUID,
    topic_ids: list[str],
    question_count: int,
    due_at: datetime.datetime | None,
    learner_ids: LearnerIdsIn,
) -> QuizAssignment:
    """Validates `topic_ids`, resolves the target-learner snapshot, and
    writes one `QuizAssignment` row, one `QuizAssignmentTarget` row per
    targeted learner, and one `QUIZ_ASSIGNMENT_CREATED` event per
    targeted learner (FR-001-FR-005, FR-015) -- all in one transaction."""
    subject_id = _resolve_assignment_subject_id(
        db, topic_ids=topic_ids, roster_subject_id=roster.subject_id
    )
    target_learner_ids = resolve_target_learner_ids(
        learner_ids, enrolled_learner_ids=_enrolled_learner_ids(db, roster_id=roster.roster_id)
    )

    assignment = QuizAssignment(
        roster_id=roster.roster_id,
        instructor_id=instructor_id,
        subject_id=subject_id,
        topic_ids=list(topic_ids),
        question_count=question_count,
        due_at=due_at,
    )
    db.add(assignment)
    db.flush()

    for learner_id in target_learner_ids:
        db.add(QuizAssignmentTarget(assignment_id=assignment.assignment_id, learner_id=learner_id))
        record_event(
            db,
            learner_id=learner_id,
            event_type=AssessmentEventType.QUIZ_ASSIGNMENT_CREATED,
            subject_id=subject_id,
            topic_id=None,
            payload={
                "assignment_id": str(assignment.assignment_id),
                "roster_id": str(roster.roster_id),
                "instructor_id": str(instructor_id),
                "topic_ids": list(topic_ids),
                "question_count": question_count,
                "due_at": due_at.isoformat() if due_at else None,
            },
        )

    db.commit()
    db.refresh(assignment)
    return assignment


def cancel_assignment(db: Session, *, assignment: QuizAssignment) -> QuizAssignment:
    """Sets `cancelled_at` (research.md §6) -- never deletes the
    assignment, its targets, or any `QuizSession`/`MasteryState`/
    `AssessmentEvent` row an already-completed attempt created (FR-012).
    Writes one `QUIZ_ASSIGNMENT_CANCELLED` event per target row that was
    not yet `completed` at this moment (FR-015, research.md §7) -- a
    learner who had already finished is not re-notified."""
    if assignment.cancelled_at is not None:
        raise ConflictError("already_cancelled")

    targets = (
        db.query(QuizAssignmentTarget)
        .filter(QuizAssignmentTarget.assignment_id == assignment.assignment_id)
        .all()
    )
    session_status_by_id: dict[uuid.UUID, QuizSessionStatus] = {}
    session_ids = [t.quiz_session_id for t in targets if t.quiz_session_id is not None]
    if session_ids:
        for quiz_session_id, status in (
            db.query(QuizSession.quiz_session_id, QuizSession.status)
            .filter(QuizSession.quiz_session_id.in_(session_ids))
            .all()
        ):
            session_status_by_id[quiz_session_id] = status

    assignment.cancelled_at = datetime.datetime.now(datetime.UTC)

    for target in targets:
        status = (
            session_status_by_id.get(target.quiz_session_id)
            if target.quiz_session_id is not None
            else None
        )
        # Only a NULL (not-started) or still-in_progress target gets a
        # cancellation event -- completed and ended_early are both
        # already-settled terminal states with nothing new to report
        # (research.md §7's exact "NULL or in_progress" condition).
        attempt_already_settled = status is not None and status != QuizSessionStatus.IN_PROGRESS
        if attempt_already_settled:
            continue
        record_event(
            db,
            learner_id=target.learner_id,
            event_type=AssessmentEventType.QUIZ_ASSIGNMENT_CANCELLED,
            subject_id=assignment.subject_id,
            topic_id=None,
            payload={
                "assignment_id": str(assignment.assignment_id),
                "roster_id": str(assignment.roster_id),
                "instructor_id": str(assignment.instructor_id),
            },
        )

    db.commit()
    db.refresh(assignment)
    return assignment
