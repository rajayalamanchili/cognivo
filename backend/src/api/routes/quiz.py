"""Adaptive-difficulty quiz endpoints (contracts/api.md, spec 005).

`POST /api/questions/{question_id}/answer` is NOT touched here -- its
quiz-aware extension lives in `questions.py` itself (research.md §4),
reusing the exact same, unmodified grading/mastery-update mechanism a
non-quiz answer already goes through.

`get_quiz_next_question` gains one conditional check for spec 011
(research.md §2): `assert_guardian_owns_assignment_session` is a no-op
for a `QuizSession` that isn't linked to a `QuizAssignmentTarget` row,
so this route's behavior for the pre-existing demo/capability-URL quiz
path (this docstring's original scope) is completely unchanged.
"""

import datetime
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.db import get_db
from src.models.enums import QuizSessionStatus
from src.models.quiz_session import QuizSession
from src.models.subject import Subject
from src.models.topic import Topic
from src.observability.session import get_database_session_service
from src.observability.tracing import traced_request
from src.services.auth.dependencies import optional_session_claims
from src.services.auth.tokens import SessionClaims
from src.services.demo_learner import get_demo_learner
from src.services.quiz.session import (
    QuizEndedEarlyError,
    compute_quiz_summary,
    generate_quiz_question,
    persist_quiz_question,
    start_quiz,
)
from src.services.quiz_assignment.assignment import assert_guardian_owns_assignment_session

router = APIRouter()

_MIN_QUESTION_COUNT = 1
_MAX_QUESTION_COUNT = 50


def _resolve_quiz_subject_id(db: Session, topic_ids: list[str]) -> str:
    """Resolves the single subject every `topic_id` must belong to
    (FR-001) -- the request has no `subject_id` field of its own, per
    contracts/api.md."""
    resolved_subject_ids: set[str] = set()
    for topic_id in topic_ids:
        topic = db.query(Topic).filter(Topic.topic_id == topic_id).first()
        if topic is None:
            raise NotFoundError(f"unknown topic_id: {topic_id!r}")
        resolved_subject_ids.add(topic.subject_id)

    if len(resolved_subject_ids) > 1:
        raise NotFoundError(f"topic_ids span more than one subject: {sorted(resolved_subject_ids)}")

    subject_id = resolved_subject_ids.pop()
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject_id


def _validate_quiz_start_request(topic_ids: list[str], question_count: int) -> None:
    if not topic_ids:
        raise UnprocessableError("topic_ids must be a non-empty list")
    if len(set(topic_ids)) != len(topic_ids):
        raise UnprocessableError("topic_ids must not contain a duplicate")
    if not (_MIN_QUESTION_COUNT <= question_count <= _MAX_QUESTION_COUNT):
        raise UnprocessableError(
            f"question_count must be between {_MIN_QUESTION_COUNT} and "
            f"{_MAX_QUESTION_COUNT} inclusive"
        )


class QuizQuestionOut(BaseModel):
    question_id: uuid.UUID
    topic_id: str
    difficulty: str
    question_type: str
    stem: str
    options: list[str] | None = None


class QuizStartIn(BaseModel):
    topic_ids: list[str]
    question_count: int


class QuizStartOut(BaseModel):
    quiz_session_id: uuid.UUID
    status: str
    question: QuizQuestionOut | None = None


@router.post("/api/quizzes", response_model=QuizStartOut)
async def start_quiz_route(body: QuizStartIn, db: Session = Depends(get_db)) -> QuizStartOut:
    _validate_quiz_start_request(body.topic_ids, body.question_count)
    subject_id = _resolve_quiz_subject_id(db, body.topic_ids)
    learner = get_demo_learner(db)

    quiz = start_quiz(
        db,
        learner_id=learner.learner_id,
        subject_id=subject_id,
        topic_ids=body.topic_ids,
        question_count=body.question_count,
    )

    try:
        with traced_request():
            result = await generate_quiz_question(
                db, quiz=quiz, session_service=get_database_session_service()
            )
    except QuizEndedEarlyError:
        quiz.status = QuizSessionStatus.ENDED_EARLY
        quiz.completed_at = datetime.datetime.now(datetime.UTC)
        db.commit()
        return QuizStartOut(quiz_session_id=quiz.quiz_session_id, status="ended_early")

    question = persist_quiz_question(
        db,
        quiz_session_id=quiz.quiz_session_id,
        learner_id=learner.learner_id,
        subject_id=subject_id,
        result=result,
    )
    db.commit()
    return QuizStartOut(
        quiz_session_id=quiz.quiz_session_id,
        status="in_progress",
        question=QuizQuestionOut(
            question_id=question.question_id,
            topic_id=result.topic_id,
            difficulty=result.difficulty.value,
            question_type=result.question_type.value,
            stem=result.draft.stem,
            options=result.draft.options,
        ),
    )


class QuizNextQuestionOut(BaseModel):
    status: str
    question: QuizQuestionOut | None = None


@router.get("/api/quizzes/{quiz_session_id}/next-question", response_model=QuizNextQuestionOut)
async def get_quiz_next_question(
    quiz_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: SessionClaims | None = Depends(optional_session_claims),
) -> QuizNextQuestionOut:
    quiz = db.get(QuizSession, quiz_session_id)
    if quiz is None:
        raise NotFoundError(f"unknown quiz_session_id: {quiz_session_id}")
    assert_guardian_owns_assignment_session(db, quiz_session_id=quiz_session_id, claims=claims)
    if quiz.status != QuizSessionStatus.IN_PROGRESS:
        raise ConflictError(
            f"quiz {quiz_session_id} is already {quiz.status.value} -- "
            "call GET /api/quizzes/{quiz_session_id} for the summary"
        )

    try:
        with traced_request():
            result = await generate_quiz_question(
                db, quiz=quiz, session_service=get_database_session_service()
            )
    except QuizEndedEarlyError:
        quiz.status = QuizSessionStatus.ENDED_EARLY
        quiz.completed_at = datetime.datetime.now(datetime.UTC)
        db.commit()
        return QuizNextQuestionOut(status="ended_early")

    question = persist_quiz_question(
        db,
        quiz_session_id=quiz.quiz_session_id,
        learner_id=quiz.learner_id,
        subject_id=quiz.subject_id,
        result=result,
    )
    db.commit()
    return QuizNextQuestionOut(
        status="in_progress",
        question=QuizQuestionOut(
            question_id=question.question_id,
            topic_id=result.topic_id,
            difficulty=result.difficulty.value,
            question_type=result.question_type.value,
            stem=result.draft.stem,
            options=result.draft.options,
        ),
    )


class QuizScoreOut(BaseModel):
    correct: int
    total: int


class QuizSummaryEntryOut(BaseModel):
    topic_id: str
    difficulty: str
    correct: int
    total: int


class QuizSummaryOut(BaseModel):
    quiz_session_id: uuid.UUID
    subject_id: str
    topic_ids: list[str]
    question_count: int
    status: str
    started_at: str
    completed_at: str | None
    score: QuizScoreOut
    summary: list[QuizSummaryEntryOut]


@router.get("/api/quizzes/{quiz_session_id}", response_model=QuizSummaryOut)
def get_quiz_summary_route(
    quiz_session_id: uuid.UUID, db: Session = Depends(get_db)
) -> QuizSummaryOut:
    quiz = db.get(QuizSession, quiz_session_id)
    if quiz is None:
        raise NotFoundError(f"unknown quiz_session_id: {quiz_session_id}")

    summary = compute_quiz_summary(db, quiz_session_id=quiz_session_id)

    return QuizSummaryOut(
        quiz_session_id=quiz.quiz_session_id,
        subject_id=quiz.subject_id,
        topic_ids=quiz.topic_ids,
        question_count=quiz.question_count,
        status=quiz.status.value,
        started_at=quiz.started_at.isoformat(),
        completed_at=quiz.completed_at.isoformat() if quiz.completed_at else None,
        score=QuizScoreOut(correct=summary.score.correct, total=summary.score.total),
        summary=[
            QuizSummaryEntryOut(
                topic_id=entry.topic_id,
                difficulty=entry.difficulty.value,
                correct=entry.correct,
                total=entry.total,
            )
            for entry in summary.breakdown
        ],
    )
