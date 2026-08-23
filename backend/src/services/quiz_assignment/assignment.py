"""Assignment creation, cancellation, target-list resolution, and
guardian-mediated attempt start (spec 011 FR-001-FR-006, FR-011-FR-016;
research.md §1/§2/§3/§4/§6/§7).

`create_assignment`/`cancel_assignment`/`start_assignment_attempt` never
modify the grading/mastery-update path, and `start_assignment_attempt`
calls `services/quiz/session.py`'s existing `start_quiz()`/
`generate_quiz_question()` unchanged -- an assignment attempt is just an
ordinary `QuizSession` (research.md §1).
"""

import datetime
import uuid
from collections.abc import Sequence
from typing import Literal

from google.adk.sessions import BaseSessionService
from sqlalchemy.orm import Session

from src.api.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.learner_profile import LearnerProfile
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.models.quiz_session import QuizSession
from src.models.topic import Topic
from src.observability.tracing import traced_request
from src.services.audit_log.writer import record_event
from src.services.auth.tokens import SessionClaims
from src.services.quiz.session import (
    QuizEndedEarlyError,
    QuizQuestionResult,
    generate_quiz_question,
    start_quiz,
)

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


def _assert_eligible_to_start(
    db: Session, *, assignment: QuizAssignment, target: QuizAssignmentTarget
) -> None:
    """FR-006/FR-011/FR-014's start-eligibility checks, in
    contracts/api.md's documented failure-mode order -- "targeted" and
    "own learner" are checked by the caller (the route) before it ever
    has a `target` row to pass in here."""
    if target.quiz_session_id is not None:
        raise ConflictError("already_attempted")
    if assignment.due_at is not None and datetime.datetime.now(datetime.UTC) > assignment.due_at:
        raise ConflictError("past_due")
    if assignment.cancelled_at is not None:
        raise ConflictError("assignment_cancelled")
    still_enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.learner_id == target.learner_id,
            Enrollment.roster_id == assignment.roster_id,
        )
        .first()
        is not None
    )
    if not still_enrolled:
        raise ForbiddenError("not_enrolled")


def _claim_target_for_quiz_session(
    db: Session, *, target: QuizAssignmentTarget, quiz_session_id: uuid.UUID
) -> bool:
    """Atomically sets `target.quiz_session_id` only if it is still
    `NULL` -- an `UPDATE ... WHERE quiz_session_id IS NULL` re-evaluates
    against the latest committed row once any concurrent racer's own
    update has released its row lock, so at most one concurrent caller
    ever wins this (research.md §3's DB-enforced single-attempt
    guarantee, same reasoning `uq_enrollments_learner_roster` documents
    for the comparable duplicate-enrollment case). Returns whether this
    call won the claim."""
    claimed_rows = (
        db.query(QuizAssignmentTarget)
        .filter(
            QuizAssignmentTarget.assignment_target_id == target.assignment_target_id,
            QuizAssignmentTarget.quiz_session_id.is_(None),
        )
        .update({QuizAssignmentTarget.quiz_session_id: quiz_session_id})
    )
    if claimed_rows == 1:
        target.quiz_session_id = quiz_session_id
        return True
    return False


async def start_assignment_attempt(
    db: Session,
    *,
    assignment: QuizAssignment,
    target: QuizAssignmentTarget,
    session_service: BaseSessionService,
) -> tuple[QuizSession, QuizQuestionResult | None]:
    """Runs start-eligibility checks, then calls the existing
    `start_quiz()`/`generate_quiz_question()` unchanged and claims
    `target.quiz_session_id` in the same transaction (FR-006, FR-011,
    FR-014; research.md §1/§2/§3). Mirrors `quiz.py`'s `start_quiz_route`
    control flow exactly (including the `QuizEndedEarlyError` branch) so
    an assigned quiz's first-question generation is behaviorally
    identical to a non-assigned one (SC-002) -- the caller (the route)
    persists the returned `QuizQuestionResult` via `persist_quiz_question`
    and commits, exactly as `quiz.py`'s own route does for a `None`-free
    result; a `None` result means the quiz already ended early and this
    function has already committed that outcome itself."""
    _assert_eligible_to_start(db, assignment=assignment, target=target)

    quiz = start_quiz(
        db,
        learner_id=target.learner_id,
        subject_id=assignment.subject_id,
        topic_ids=assignment.topic_ids,
        question_count=assignment.question_count,
    )

    if not _claim_target_for_quiz_session(db, target=target, quiz_session_id=quiz.quiz_session_id):
        db.rollback()
        raise ConflictError("already_attempted")

    try:
        with traced_request():
            result = await generate_quiz_question(db, quiz=quiz, session_service=session_service)
    except QuizEndedEarlyError:
        quiz.status = QuizSessionStatus.ENDED_EARLY
        quiz.completed_at = datetime.datetime.now(datetime.UTC)
        db.commit()
        return quiz, None

    return quiz, result


def assert_guardian_owns_assignment_session(
    db: Session, *, quiz_session_id: uuid.UUID, claims: SessionClaims | None
) -> None:
    """No-op unless `quiz_session_id` is linked to a `QuizAssignmentTarget`
    row (research.md §2) -- the pre-existing, non-assignment quiz/answer
    path is completely unaffected. When it *is* assignment-linked, the
    request must carry a guardian session matching that target's
    learner's own `guardian_id`, or this raises `ForbiddenError`
    (`not_learner_guardian`)."""
    target = (
        db.query(QuizAssignmentTarget)
        .filter(QuizAssignmentTarget.quiz_session_id == quiz_session_id)
        .first()
    )
    if target is None:
        return

    if claims is None or claims.account_type != "guardian":
        raise ForbiddenError("not_learner_guardian")

    learner = db.get(LearnerProfile, target.learner_id)
    if learner is None or learner.guardian_id != claims.account_id:
        raise ForbiddenError("not_learner_guardian")


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
