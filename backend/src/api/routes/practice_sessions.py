"""Timed practice session endpoints (spec 022, contracts/api.md).

Ordinary untimed practice keeps using `GET /api/learners/{learner_id}/
next-question` (`questions.py`) directly, unchanged (FR-009) -- these
routes exist only for the timed path (FR-008), reusing that same
route's question-generation logic (`generate_and_persist_next_question`)
with `practice_session_id` tagging as the only difference.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ConflictError, NotFoundError
from src.api.routes.questions import (
    NextQuestionOut,
    build_next_question_out,
    generate_and_persist_next_question,
    has_placement_data,
)
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuizSessionStatus
from src.models.generated_question import GeneratedQuestion
from src.models.practice_session import PracticeSession
from src.models.subject import Subject
from src.services.quiz.session import (
    SessionAlreadyEndedError,
    check_and_expire_if_needed,
    compute_timed_session_timing,
    end_session_manually,
    session_expires_at,
    validate_time_limit_seconds,
)

router = APIRouter()


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


def _get_practice_session(db: Session, practice_session_id: uuid.UUID) -> PracticeSession:
    # No access-control check here (unlike quiz.py's routes, which all
    # call assert_quiz_session_access), deliberately -- practice sessions
    # are never assignment-linked, matching questions.py's existing
    # get_next_question pattern. Revisit if that ever changes.
    session = db.get(PracticeSession, practice_session_id)
    if session is None:
        raise NotFoundError(f"unknown practice_session_id: {practice_session_id}")
    return session


def _compute_practice_score(db: Session, *, practice_session_id: uuid.UUID) -> tuple[int, int]:
    """Simple correct/total count (contracts/api.md) -- unlike a quiz,
    practice has no per-(topic, difficulty) breakdown to report."""
    rows = (
        db.query(AssessmentEvent)
        .join(
            GeneratedQuestion, AssessmentEvent.question_id == GeneratedQuestion.question_id
        )
        .filter(
            GeneratedQuestion.practice_session_id == practice_session_id,
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .all()
    )
    total = len(rows)
    correct = sum(1 for event in rows if bool(event.payload["correct"]))
    return correct, total


class PracticeStartIn(BaseModel):
    learner_id: uuid.UUID
    subject_id: str
    time_limit_seconds: int


class PracticeStartOut(BaseModel):
    practice_session_id: uuid.UUID
    status: str
    expires_at: str
    question: NextQuestionOut


@router.post("/api/practice-sessions", response_model=PracticeStartOut)
async def start_practice_session(
    body: PracticeStartIn, db: Session = Depends(get_db)
) -> PracticeStartOut:
    # time_limit_seconds's `int` (not `int | None`) type already makes
    # Pydantic reject a missing/null value with a 422 -- only the
    # preset-membership check is left to do here.
    validate_time_limit_seconds(body.time_limit_seconds)
    _get_validated_subject(db, body.subject_id)

    if not has_placement_data(db, learner_id=body.learner_id, subject_id=body.subject_id):
        raise NotFoundError(
            f"learner {body.learner_id} has no placement data for subject "
            f"{body.subject_id!r} yet -- complete placement first"
        )

    practice_session = PracticeSession(
        learner_id=body.learner_id,
        subject_id=body.subject_id,
        time_limit_seconds=body.time_limit_seconds,
        status=QuizSessionStatus.IN_PROGRESS,
    )
    db.add(practice_session)
    db.flush()

    question, result = await generate_and_persist_next_question(
        db,
        learner_id=body.learner_id,
        subject_id=body.subject_id,
        practice_session_id=practice_session.practice_session_id,
    )
    db.commit()

    # Every PracticeSession is timed by construction (time_limit_seconds
    # is a required field above), so this is never None here.
    expires_at = session_expires_at(practice_session)
    assert expires_at is not None
    return PracticeStartOut(
        practice_session_id=practice_session.practice_session_id,
        status="in_progress",
        expires_at=expires_at,
        question=build_next_question_out(
            db,
            question=question,
            result=result,
            learner_id=body.learner_id,
            subject_id=body.subject_id,
        ),
    )


class PracticeNextQuestionOut(BaseModel):
    status: str
    question: NextQuestionOut | None = None
    expires_at: str | None = None


@router.get(
    "/api/practice-sessions/{practice_session_id}/next-question",
    response_model=PracticeNextQuestionOut,
)
async def get_practice_next_question(
    practice_session_id: uuid.UUID, db: Session = Depends(get_db)
) -> PracticeNextQuestionOut:
    practice_session = _get_practice_session(db, practice_session_id)
    check_and_expire_if_needed(db, session=practice_session, session_type="practice")
    if practice_session.status != QuizSessionStatus.IN_PROGRESS:
        raise ConflictError(
            f"practice session {practice_session_id} is already "
            f"{practice_session.status.value} -- call "
            "GET /api/practice-sessions/{practice_session_id} for the summary"
        )

    question, result = await generate_and_persist_next_question(
        db,
        learner_id=practice_session.learner_id,
        subject_id=practice_session.subject_id,
        practice_session_id=practice_session.practice_session_id,
    )
    db.commit()

    return PracticeNextQuestionOut(
        status="in_progress",
        question=build_next_question_out(
            db,
            question=question,
            result=result,
            learner_id=practice_session.learner_id,
            subject_id=practice_session.subject_id,
        ),
        expires_at=session_expires_at(practice_session),
    )


class PracticeEndOut(BaseModel):
    practice_session_id: uuid.UUID
    status: str


@router.post("/api/practice-sessions/{practice_session_id}/end", response_model=PracticeEndOut)
def end_practice_session(
    practice_session_id: uuid.UUID, db: Session = Depends(get_db)
) -> PracticeEndOut:
    """Manual early-end (spec 022 FR-010). No "untimed" `404` case --
    every `PracticeSession` row is timed by construction (`SessionNotTimedError`
    can never actually be raised here, unlike the quiz route)."""
    practice_session = _get_practice_session(db, practice_session_id)
    # PR feedback: run the lazy expiry check first so a deadline that
    # already silently passed is recorded as `timer_expired`, not
    # mislabeled `manually_ended_early` just because this click reached
    # the server first.
    check_and_expire_if_needed(db, session=practice_session, session_type="practice")
    try:
        end_session_manually(db, session=practice_session, session_type="practice")
    except SessionAlreadyEndedError as exc:
        raise ConflictError(str(exc)) from exc
    db.commit()
    return PracticeEndOut(
        practice_session_id=practice_session.practice_session_id,
        status=practice_session.status.value,
    )


class PracticeScoreOut(BaseModel):
    correct: int
    total: int


class PracticeSummaryOut(BaseModel):
    practice_session_id: uuid.UUID
    subject_id: str
    status: str
    started_at: str
    completed_at: str | None
    score: PracticeScoreOut
    # Spec 022 SC-005 (US3, T036): always non-null -- every
    # PracticeSession row is timed by construction.
    time_limit_seconds: int | None = None
    elapsed_seconds: int | None = None
    end_reason: str | None = None


@router.get("/api/practice-sessions/{practice_session_id}", response_model=PracticeSummaryOut)
def get_practice_summary(
    practice_session_id: uuid.UUID, db: Session = Depends(get_db)
) -> PracticeSummaryOut:
    practice_session = _get_practice_session(db, practice_session_id)
    # Spec 022 FR-003: a timed practice session whose deadline passed with
    # no intervening next-question/answer call must still show as expired
    # here, not just on those other two endpoints.
    check_and_expire_if_needed(db, session=practice_session, session_type="practice")
    correct, total = _compute_practice_score(db, practice_session_id=practice_session_id)
    timing = compute_timed_session_timing(db, session=practice_session, session_type="practice")

    return PracticeSummaryOut(
        practice_session_id=practice_session.practice_session_id,
        subject_id=practice_session.subject_id,
        status=practice_session.status.value,
        started_at=practice_session.started_at.isoformat(),
        completed_at=(
            practice_session.completed_at.isoformat() if practice_session.completed_at else None
        ),
        score=PracticeScoreOut(correct=correct, total=total),
        time_limit_seconds=timing.time_limit_seconds,
        elapsed_seconds=timing.elapsed_seconds,
        end_reason=timing.end_reason,
    )
