"""Tutor Agent conversational endpoints (spec 012, contracts/api.md).

Auth (FR-001): guardian-mediated, targeting one of that guardian's own
real learners (same ownership-check-collapses-404-into-403 shape as
`quiz_assignments.py`'s `_get_own_learner`, to avoid learner-id
enumeration) -- or the seeded demo learner, matching every other
demo-learner-exclusive endpoint (`is_demo=True` needs no session at
all).
"""

import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ForbiddenError, NotFoundError
from src.db import get_db
from src.models.classroom_roster import ClassroomRoster
from src.models.content_passage_embedding import ContentPassageEmbedding
from src.models.enrollment import Enrollment
from src.models.learner_profile import LearnerProfile
from src.models.subject import Subject
from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession
from src.services.auth.dependencies import optional_session_claims
from src.services.auth.tokens import SessionClaims
from src.services.tutor.session import open_session, prepare_message, stream_message_response

router = APIRouter()


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    """Mirrors `questions.py`'s helper of the same name."""
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


def _authorize_learner(
    db: Session, *, learner_id: uuid.UUID, claims: SessionClaims | None
) -> LearnerProfile:
    """FR-001: the demo learner needs no session at all; a real learner
    requires a guardian session that owns it. A nonexistent learner_id
    and one that exists but isn't owned by the caller both collapse to
    the same `403 not_your_learner` (mirrors `quiz_assignments.py`'s
    `_get_own_learner` -- doesn't reveal via a 404 whether the id exists
    at all)."""
    learner = db.get(LearnerProfile, learner_id)
    if learner is not None and learner.is_demo:
        return learner
    if (
        learner is None
        or claims is None
        or claims.account_type != "guardian"
        or learner.guardian_id != claims.account_id
    ):
        raise ForbiddenError("not_your_learner")
    return learner


class OpenSessionIn(BaseModel):
    learner_id: uuid.UUID
    subject_id: str


class OpenSessionOut(BaseModel):
    session_id: uuid.UUID
    subject_id: str
    status: str


@router.post("/api/tutor/sessions", response_model=OpenSessionOut)
def open_session_route(
    body: OpenSessionIn,
    response: Response,
    claims: SessionClaims | None = Depends(optional_session_claims),
    db: Session = Depends(get_db),
) -> OpenSessionOut:
    learner = _authorize_learner(db, learner_id=body.learner_id, claims=claims)
    _get_validated_subject(db, body.subject_id)

    guardian_id = (
        claims.account_id if claims is not None and claims.account_type == "guardian" else None
    )
    session, created = open_session(
        db, learner_id=learner.learner_id, subject_id=body.subject_id, guardian_id=guardian_id
    )
    response.status_code = 201 if created else 200
    return OpenSessionOut(
        session_id=session.session_id, subject_id=session.subject_id, status=session.status.value
    )


class SubmitMessageIn(BaseModel):
    question: str


@router.post("/api/tutor/sessions/{session_id}/messages")
async def submit_message_route(
    session_id: uuid.UUID,
    body: SubmitMessageIn,
    claims: SessionClaims | None = Depends(optional_session_claims),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    session = db.get(TutoringSession, session_id)
    if session is None:
        raise NotFoundError(f"unknown session_id: {session_id}")
    _authorize_learner(db, learner_id=session.learner_id, claims=claims)

    # Every check, retrieval, and the A2A connection itself all happen
    # here, before any byte is streamed (services/tutor/session.py's
    # module docstring) -- a rejection raises a normal domain error,
    # producing a clean 409/429/422/503 JSON response.
    prepared = await prepare_message(db, session=session, question=body.question)
    return StreamingResponse(
        stream_message_response(db, prepared=prepared), media_type="text/event-stream"
    )


def _instructor_teaches_learner(
    db: Session, *, learner_id: uuid.UUID, subject_id: str, instructor_id: uuid.UUID
) -> bool:
    """Mirrors `content_review/resolution.py`'s `_question_belongs_to_instructor`
    -- same enrollment-scoped access (real or demo instructor, both
    resolve through `current_instructor`'s unified `.instructor_id`)."""
    return (
        db.query(ClassroomRoster)
        .join(Enrollment, Enrollment.roster_id == ClassroomRoster.roster_id)
        .filter(
            Enrollment.learner_id == learner_id,
            ClassroomRoster.instructor_id == instructor_id,
            ClassroomRoster.subject_id == subject_id,
        )
        .first()
        is not None
    )


def _authorize_exchange_inspection(
    db: Session, *, session: TutoringSession, claims: SessionClaims | None
) -> None:
    """US3 auth (contracts/api.md): the owning guardian, the learner's
    enrolled-classroom instructor, or the demo-instructor session --
    deliberately no demo-learner no-auth carve-out here (unlike the
    session/message endpoints' FR-001): inspection is instructor/
    guardian-facing, not something the anonymous demo-learner UI itself
    calls."""
    if claims is not None and claims.account_type == "guardian":
        if session.guardian_id == claims.account_id:
            return
        raise ForbiddenError("not_your_learner")
    if claims is not None and claims.account_type in ("instructor", "demo_instructor"):
        if _instructor_teaches_learner(
            db,
            learner_id=session.learner_id,
            subject_id=session.subject_id,
            instructor_id=claims.account_id,
        ):
            return
        raise ForbiddenError("not_learner_instructor")
    raise ForbiddenError("not_authorized")


def _derive_exchange_status(exchange: TutorExchange) -> str:
    """Derived, never stored (contracts/api.md) -- `answer_text`/
    `failed_at` are mutually exclusive (data-model.md's validation
    rules), so exactly one of the three states always applies."""
    if exchange.answer_text is not None:
        return "completed"
    if exchange.failed_at is not None:
        return "failed"
    return "in_progress"


class RetrievedPassageOut(BaseModel):
    passage_id: uuid.UUID
    topic_id: str
    field: str
    text: str


class ExchangeOut(BaseModel):
    exchange_id: uuid.UUID
    status: str
    question_text: str
    answer_text: str | None
    grounded: bool
    retrieved_passages: list[RetrievedPassageOut]
    delegation_context: list[dict]


@router.get("/api/tutor/exchanges/{exchange_id}", response_model=ExchangeOut)
def get_exchange_route(
    exchange_id: uuid.UUID,
    claims: SessionClaims | None = Depends(optional_session_claims),
    db: Session = Depends(get_db),
) -> ExchangeOut:
    exchange = db.get(TutorExchange, exchange_id)
    if exchange is None:
        raise NotFoundError(f"unknown exchange_id: {exchange_id}")
    session = db.get(TutoringSession, exchange.session_id)
    _authorize_exchange_inspection(db, session=session, claims=claims)

    # retrieved_passage_ids is already the grounded, in-order subset
    # (data-model.md) -- fetched here, not cached on the row, since
    # ContentPassageEmbedding.text can only get stale by a content
    # reload superseding it (data-model.md's upsert discipline), never
    # by this read.
    passages_by_id = {
        passage.passage_id: passage
        for passage in db.query(ContentPassageEmbedding).filter(
            ContentPassageEmbedding.passage_id.in_(exchange.retrieved_passage_ids)
        )
    }
    retrieved_passages = [
        RetrievedPassageOut(
            passage_id=passage.passage_id,
            topic_id=passage.topic_id,
            field=passage.field.value,
            text=passage.text,
        )
        for passage_id in exchange.retrieved_passage_ids
        if (passage := passages_by_id.get(passage_id)) is not None
    ]

    return ExchangeOut(
        exchange_id=exchange.exchange_id,
        status=_derive_exchange_status(exchange),
        question_text=exchange.question_text,
        answer_text=exchange.answer_text,
        grounded=exchange.grounded,
        retrieved_passages=retrieved_passages,
        delegation_context=exchange.delegation_context or [],
    )
