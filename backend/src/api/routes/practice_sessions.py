"""Timed practice session endpoints (spec 022, contracts/api.md).

Ordinary untimed practice keeps using `GET /api/learners/{learner_id}/
next-question` (`questions.py`) directly, unchanged (FR-009) -- these
routes exist only for the timed path (FR-008), reusing that same
route's question-generation logic (`generate_and_persist_next_question`)
with `practice_session_id` tagging as the only difference.
"""

import datetime
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ConflictError, NotFoundError
from src.api.routes.questions import (
    NextQuestionOut,
    generate_and_persist_next_question,
)
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuestionType, QuizSessionStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState
from src.models.practice_session import PracticeSession
from src.models.subject import Subject
from src.services.mediation.grade import resolve_unlocked_grade
from src.services.mediation.read_aloud import resolve_read_aloud_eligible
from src.services.quiz.session import (
    SessionAlreadyEndedError,
    check_and_expire_if_needed,
    end_session_manually,
    validate_time_limit_seconds,
)

router = APIRouter()


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


def _get_practice_session(db: Session, practice_session_id: uuid.UUID) -> PracticeSession:
    session = db.get(PracticeSession, practice_session_id)
    if session is None:
        raise NotFoundError(f"unknown practice_session_id: {practice_session_id}")
    return session


def _practice_expires_at(session: PracticeSession) -> str:
    return (session.started_at + datetime.timedelta(seconds=session.time_limit_seconds)).isoformat()


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

    has_placement_data = (
        db.query(MasteryState)
        .filter(
            MasteryState.learner_id == body.learner_id, MasteryState.subject_id == body.subject_id
        )
        .first()
        is not None
    )
    if not has_placement_data:
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

    return PracticeStartOut(
        practice_session_id=practice_session.practice_session_id,
        status="in_progress",
        expires_at=_practice_expires_at(practice_session),
        question=NextQuestionOut(
            question_id=question.question_id,
            topic_id=result.selection.topic_id,
            difficulty=result.selection.difficulty.value,
            question_type=result.question_type.value,
            stem=result.draft.stem,
            options=result.draft.options,
            image_url=result.image_url,
            image_alt_text=result.image_alt_text,
            steps=(
                [step.step_prompt for step in result.draft.steps]
                if result.question_type == QuestionType.MULTI_STEP
                else None
            ),
            read_aloud_eligible=resolve_read_aloud_eligible(
                db, learner_id=body.learner_id, subject_id=body.subject_id
            ),
            unlocked_grade=resolve_unlocked_grade(
                db, learner_id=body.learner_id, subject_id=body.subject_id
            ),
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
    if check_and_expire_if_needed(db, session=practice_session, session_type="practice"):
        db.commit()
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
        question=NextQuestionOut(
            question_id=question.question_id,
            topic_id=result.selection.topic_id,
            difficulty=result.selection.difficulty.value,
            question_type=result.question_type.value,
            stem=result.draft.stem,
            options=result.draft.options,
            image_url=result.image_url,
            image_alt_text=result.image_alt_text,
            steps=(
                [step.step_prompt for step in result.draft.steps]
                if result.question_type == QuestionType.MULTI_STEP
                else None
            ),
            read_aloud_eligible=resolve_read_aloud_eligible(
                db, learner_id=practice_session.learner_id, subject_id=practice_session.subject_id
            ),
            unlocked_grade=resolve_unlocked_grade(
                db, learner_id=practice_session.learner_id, subject_id=practice_session.subject_id
            ),
        ),
        expires_at=_practice_expires_at(practice_session),
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
    """Baseline shape (spec 022 T029) -- extended with
    `time_limit_seconds`/`elapsed_seconds`/`end_reason` by User Story 3
    (T036), not here."""

    practice_session_id: uuid.UUID
    subject_id: str
    status: str
    started_at: str
    completed_at: str | None
    score: PracticeScoreOut


@router.get("/api/practice-sessions/{practice_session_id}", response_model=PracticeSummaryOut)
def get_practice_summary(
    practice_session_id: uuid.UUID, db: Session = Depends(get_db)
) -> PracticeSummaryOut:
    practice_session = _get_practice_session(db, practice_session_id)
    correct, total = _compute_practice_score(db, practice_session_id=practice_session_id)

    return PracticeSummaryOut(
        practice_session_id=practice_session.practice_session_id,
        subject_id=practice_session.subject_id,
        status=practice_session.status.value,
        started_at=practice_session.started_at.isoformat(),
        completed_at=(
            practice_session.completed_at.isoformat() if practice_session.completed_at else None
        ),
        score=PracticeScoreOut(correct=correct, total=total),
    )
