"""Adaptive-difficulty quiz endpoints (contracts/api.md, spec 005).

`POST /api/questions/{question_id}/answer` is NOT touched here -- its
quiz-aware extension lives in `questions.py` itself (research.md §4),
reusing the exact same, unmodified grading/mastery-update mechanism a
non-quiz answer already goes through.

`get_quiz_next_question` gains one conditional check for spec 011
(research.md §2), extended by spec 019 with tier-aware hand-off-token
support: `assert_quiz_session_access` is a no-op for a `QuizSession`
that isn't linked to a `QuizAssignmentTarget` row, so this route's
behavior for the pre-existing demo/capability-URL quiz path (this
docstring's original scope) is completely unchanged.
"""

import datetime
import uuid

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.db import get_db
from src.models.enums import QuizSessionStatus
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.models.quiz_session import QuizSession
from src.models.subject import Subject
from src.models.topic import Topic
from src.observability.session import get_database_session_service
from src.observability.tracing import traced_request
from src.services.auth.dependencies import optional_session_claims
from src.services.auth.tokens import SessionClaims
from src.services.demo_learner import get_demo_learner
from src.services.mediation.grade import resolve_unlocked_grade
from src.services.mediation.read_aloud import resolve_read_aloud_eligible
from src.services.quiz.session import (
    QuizEndedEarlyError,
    SessionAlreadyEndedError,
    SessionNotTimedError,
    check_and_expire_if_needed,
    compute_quiz_summary,
    end_session_manually,
    generate_quiz_question,
    persist_quiz_question,
    start_quiz,
    validate_time_limit_seconds,
)
from src.services.quiz_assignment.assignment import (
    assert_quiz_session_access,
    assert_quiz_summary_access,
    guardian_owns_target,
)

router = APIRouter()

_MIN_QUESTION_COUNT = 1
_MAX_QUESTION_COUNT = 50


def _quiz_expires_at(quiz: QuizSession) -> str | None:
    """`expires_at = started_at + time_limit_seconds` (research.md §1),
    `None` for an untimed quiz."""
    if quiz.time_limit_seconds is None:
        return None
    return (quiz.started_at + datetime.timedelta(seconds=quiz.time_limit_seconds)).isoformat()


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
    image_url: str | None = None
    image_alt_text: str | None = None
    read_aloud_eligible: bool = False
    unlocked_grade: int | None = None


class QuizStartIn(BaseModel):
    topic_ids: list[str]
    question_count: int
    # Spec 022 FR-001/FR-009: omitted/null = untimed, unchanged default.
    time_limit_seconds: int | None = None


class QuizStartOut(BaseModel):
    quiz_session_id: uuid.UUID
    status: str
    question: QuizQuestionOut | None = None
    # spec 019 FR-005a/b, contracts/api.md: shared with the demo/ad-hoc
    # `start_quiz_route` below, which never sets this (always `None`,
    # since a non-assignment-linked session never goes through tier
    # determination at all -- FR-014).
    handoff_token: str | None = None
    # Spec 022 FR-002/contracts/api.md: `None` for an untimed quiz.
    expires_at: str | None = None


@router.post("/api/quizzes", response_model=QuizStartOut)
async def start_quiz_route(body: QuizStartIn, db: Session = Depends(get_db)) -> QuizStartOut:
    _validate_quiz_start_request(body.topic_ids, body.question_count)
    validate_time_limit_seconds(body.time_limit_seconds)
    subject_id = _resolve_quiz_subject_id(db, body.topic_ids)
    learner = get_demo_learner(db)

    quiz = start_quiz(
        db,
        learner_id=learner.learner_id,
        subject_id=subject_id,
        topic_ids=body.topic_ids,
        question_count=body.question_count,
        time_limit_seconds=body.time_limit_seconds,
    )

    try:
        with traced_request(learner_id=learner.learner_id, session_id=quiz.quiz_session_id):
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
            image_url=result.image_url,
            image_alt_text=result.image_alt_text,
            read_aloud_eligible=resolve_read_aloud_eligible(
                db, learner_id=learner.learner_id, subject_id=subject_id
            ),
            unlocked_grade=resolve_unlocked_grade(
                db, learner_id=learner.learner_id, subject_id=subject_id
            ),
        ),
        expires_at=_quiz_expires_at(quiz),
    )


class QuizNextQuestionOut(BaseModel):
    status: str
    question: QuizQuestionOut | None = None
    expires_at: str | None = None


@router.get("/api/quizzes/{quiz_session_id}/next-question", response_model=QuizNextQuestionOut)
async def get_quiz_next_question(
    quiz_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: SessionClaims | None = Depends(optional_session_claims),
    x_quiz_handoff_token: str | None = Header(default=None),
) -> QuizNextQuestionOut:
    quiz = db.get(QuizSession, quiz_session_id)
    if quiz is None:
        raise NotFoundError(f"unknown quiz_session_id: {quiz_session_id}")
    assert_quiz_session_access(
        db, quiz_session_id=quiz_session_id, claims=claims, handoff_token=x_quiz_handoff_token
    )
    # Spec 022 FR-003/research.md §1: a no-op for an untimed quiz or one
    # already not in_progress; commits only when it actually just
    # transitioned the session, so that transition survives even though
    # the ConflictError below aborts the rest of this request.
    if check_and_expire_if_needed(db, session=quiz, session_type="quiz"):
        db.commit()
    if quiz.status != QuizSessionStatus.IN_PROGRESS:
        raise ConflictError(
            f"quiz {quiz_session_id} is already {quiz.status.value} -- "
            "call GET /api/quizzes/{quiz_session_id} for the summary"
        )

    try:
        with traced_request(learner_id=quiz.learner_id, session_id=quiz.quiz_session_id):
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
            image_url=result.image_url,
            image_alt_text=result.image_alt_text,
            read_aloud_eligible=resolve_read_aloud_eligible(
                db, learner_id=quiz.learner_id, subject_id=quiz.subject_id
            ),
            unlocked_grade=resolve_unlocked_grade(
                db, learner_id=quiz.learner_id, subject_id=quiz.subject_id
            ),
        ),
        expires_at=_quiz_expires_at(quiz),
    )


class QuizEndOut(BaseModel):
    quiz_session_id: uuid.UUID
    status: str


@router.post("/api/quizzes/{quiz_session_id}/end", response_model=QuizEndOut)
def end_quiz_route(
    quiz_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: SessionClaims | None = Depends(optional_session_claims),
    x_quiz_handoff_token: str | None = Header(default=None),
) -> QuizEndOut:
    """Manual early-end (spec 022 FR-010, research.md §4) -- new for
    timed quizzes only; `404` for an untimed quiz (nothing to end
    early), `409` if already `completed`/`ended_early`."""
    quiz = db.get(QuizSession, quiz_session_id)
    if quiz is None:
        raise NotFoundError(f"unknown quiz_session_id: {quiz_session_id}")
    assert_quiz_session_access(
        db, quiz_session_id=quiz_session_id, claims=claims, handoff_token=x_quiz_handoff_token
    )
    try:
        end_session_manually(db, session=quiz, session_type="quiz")
    except SessionNotTimedError as exc:
        raise NotFoundError(str(exc)) from exc
    except SessionAlreadyEndedError as exc:
        raise ConflictError(str(exc)) from exc
    db.commit()
    return QuizEndOut(quiz_session_id=quiz.quiz_session_id, status=quiz.status.value)


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
    quiz_session_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: SessionClaims | None = Depends(optional_session_claims),
    x_quiz_handoff_token: str | None = Header(default=None),
) -> QuizSummaryOut:
    quiz = db.get(QuizSession, quiz_session_id)
    if quiz is None:
        raise NotFoundError(f"unknown quiz_session_id: {quiz_session_id}")
    assert_quiz_summary_access(
        db, quiz_session_id=quiz_session_id, claims=claims, handoff_token=x_quiz_handoff_token
    )

    # spec 019 FR-006/FR-007a, research.md Decision 7: a no-op unless
    # assignment-linked (mirrors `assert_quiz_session_access`'s existing
    # no-op-for-demo/ad-hoc-sessions precedent) -- set for any tier,
    # unconditionally, since the badge's tier-gating happens at the
    # list-view read layer (`list_learner_assignments_route`), not here.
    #
    # Code-review fix: only when the *guardian's own* session made this
    # call, not merely when `assert_quiz_summary_access` passed -- that
    # check also accepts a hand-off token, and `LearnerAssignments.tsx`
    # calls this route automatically the instant a quiz session ends,
    # on the learner's own device. Stamping unconditionally meant a
    # check-in/opt-in-nudges/independent learner's own device cleared
    # the guardian's unviewed-activity indicator before the guardian
    # ever looked at anything -- defeating FR-006/007/008's purpose.
    target = (
        db.query(QuizAssignmentTarget)
        .filter(QuizAssignmentTarget.quiz_session_id == quiz_session_id)
        .first()
    )
    if (
        target is not None
        and target.guardian_viewed_at is None
        and guardian_owns_target(db, target=target, claims=claims)
    ):
        target.guardian_viewed_at = datetime.datetime.now(datetime.UTC)
        db.commit()

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
