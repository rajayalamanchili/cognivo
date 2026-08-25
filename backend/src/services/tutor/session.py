"""Tutoring-session orchestration: get-or-create (FR-014), and a
question's full request-assembly -> stream -> persist lifecycle
(contracts/api.md's `POST /api/tutor/sessions/{id}/messages`).

Split into two phases, both used by `api/routes/tutor.py`:

1. `prepare_message` -- every synchronous pre-stream check (FR-013/
   FR-014/FR-015, length/moderation), retrieval, and opening the Tutor
   Agent's A2A stream through its first event. All of this runs BEFORE
   the route constructs a `StreamingResponse` -- a rejection here
   (409/429/422/503) is a normal JSON error response with the right
   status code, not a broken partially-started HTTP stream (Starlette
   commits to a response's status the moment the first ASGI message is
   sent, so a `StreamingResponse` can't change its mind after that).
2. `stream_message_response` -- the actual SSE body, proxying answer
   deltas and persisting the exchange (success or failure) once the
   Tutor Agent's stream ends (FR-002/FR-003/FR-004/FR-005/FR-007/
   FR-008/FR-012, closes `/speckit-analyze` finding H2).
"""

import datetime
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.agents.recommendation.agent import build_weak_area_report
from src.api.errors import (
    ModerationRejectedError,
    QuestionTooLongError,
    RateLimitedError,
    StillAnsweringError,
)
from src.models.enums import AssessmentEventType, TutoringSessionStatus
from src.models.tutor_exchange import TutorExchange
from src.models.tutoring_session import TutoringSession
from src.observability.session import get_database_session_service
from src.observability.tracing import traced_request
from src.services.audit_log.writer import record_event
from src.services.grading_client.moderation import check_moderation
from src.services.retrieval.passage_search import search_passages
from src.services.tutor.rate_limit import check_tutor_rate_limit
from src.services.tutor_agent_client.client import (
    TutorAnswerDelta,
    TutorAnswerResult,
    TutorStreamEvent,
    TutorStreamInterruptedError,
    TutorUnavailableError,
    stream_tutor_answer,
)

# The backend's own pre-check on the learner's raw question (contracts/
# api.md's `422 question_too_long`) -- distinct from tutor-agent/'s own
# much larger MAX_REQUEST_LENGTH compensating-control cap on the whole
# bundled A2A payload (guardrails.py).
MAX_QUESTION_LENGTH = 2000

# FR-006: a simple, deterministic keyword check for whether a question
# depends on the learner's own recorded performance -- Constitution
# Principle I requires the *answer* come from the real mastery model
# when it does, not that this routing decision itself use one (an LLM
# call here would add cost/latency to decide something a fixed set of
# representative phrases already covers for this milestone's scope).
_PERFORMANCE_CONTEXT_TRIGGERS = (
    "what should i work on",
    "what to work on",
    "what should i study",
    "what do i need to improve",
    "struggling with",
    "am i struggling",
    "weak area",
    "why do i keep getting",
    "why am i getting",
    "why do i get",
    "my progress",
    "my mastery",
    "how am i doing",
    "next step",
)


def _question_needs_performance_context(question: str) -> bool:
    lowered = question.lower()
    return any(trigger in lowered for trigger in _PERFORMANCE_CONTEXT_TRIGGERS)


def _build_recommendation_delegation(db: Session, session: TutoringSession) -> dict:
    """One `{agent, request, response}` delegation-context record (FR-006,
    `/speckit-analyze` finding M1's structured shape) -- `response` is a
    reasonable summary of `WeakAreaReport`, not the full dataclass dump
    (per-answer evidence citations already live in each answer's own
    `AssessmentEvent`, not duplicated here)."""
    report = build_weak_area_report(
        db, learner_id=session.learner_id, subject_id=session.subject_id
    )
    return {
        "agent": "recommendation",
        "request": {"learner_id": str(session.learner_id), "subject_id": session.subject_id},
        "response": {
            "data_sufficiency": report.data_sufficiency,
            "broad_review_needed": report.broad_review_needed,
            "weak_areas": [
                {
                    "topic_id": flag.topic_id,
                    "display_name": flag.display_name,
                    "p_mastery": flag.p_mastery,
                    "next_step_topic_id": flag.next_step.recommended_topic_id,
                }
                for flag in report.weak_areas
            ],
            "in_progress_topic_ids": list(report.in_progress_topic_ids),
            "not_yet_assessed_topic_ids": list(report.not_yet_assessed_topic_ids),
            "insufficient_data_topic_ids": list(report.insufficient_data_topic_ids),
        },
    }


def _find_active_session(
    db: Session, *, learner_id: uuid.UUID, subject_id: str
) -> TutoringSession | None:
    return (
        db.query(TutoringSession)
        .filter(
            TutoringSession.learner_id == learner_id,
            TutoringSession.subject_id == subject_id,
            TutoringSession.status == TutoringSessionStatus.ACTIVE,
        )
        .first()
    )


def open_session(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    guardian_id: uuid.UUID | None = None,
) -> tuple[TutoringSession, bool]:
    """Get-or-create against the partial unique index (FR-014). Returns
    `(session, created)` -- `created=False` covers both "an active
    session already existed" and "a concurrent request won the DB-level
    uniqueness race" (contracts/api.md's `200` branch)."""
    existing = _find_active_session(db, learner_id=learner_id, subject_id=subject_id)
    if existing is not None:
        return existing, False

    session = TutoringSession(learner_id=learner_id, subject_id=subject_id, guardian_id=guardian_id)
    db.add(session)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = _find_active_session(db, learner_id=learner_id, subject_id=subject_id)
        if existing is not None:
            return existing, False
        raise
    db.commit()
    return session, True


def _in_flight_exchange(db: Session, *, session_id: uuid.UUID) -> TutorExchange | None:
    """FR-015's in-flight marker: `answer_text IS NULL AND failed_at IS
    NULL` on this session's most recent exchange (data-model.md, closes
    finding H2 -- a previously `failed_at`-marked exchange never blocks
    a new question)."""
    return (
        db.query(TutorExchange)
        .filter(
            TutorExchange.session_id == session_id,
            TutorExchange.answer_text.is_(None),
            TutorExchange.failed_at.is_(None),
        )
        .first()
    )


@dataclass(frozen=True)
class PreparedTutorMessage:
    session: TutoringSession
    exchange: TutorExchange
    stream: AsyncIterator[TutorStreamEvent]
    first_event: TutorStreamEvent


async def prepare_message(
    db: Session, *, session: TutoringSession, question: str
) -> PreparedTutorMessage:
    """Runs contracts/api.md's server steps, in its documented order
    (cheapest/most-likely-to-reject first): in-flight (FR-015) -> rate
    limit (FR-013) -> length/moderation -> retrieval (FR-002/FR-012) ->
    bundle -> open the A2A stream. Raises `StillAnsweringError`/
    `RateLimitedError`/`QuestionTooLongError`/`ModerationRejectedError`/
    `TutorUnavailableError` -- the caller (the route) must not construct
    a `StreamingResponse` until this returns successfully.
    """
    in_flight = _in_flight_exchange(db, session_id=session.session_id)
    if in_flight is not None:
        raise StillAnsweringError(exchange_id=in_flight.exchange_id)

    rate_limit_status = check_tutor_rate_limit(db, learner_id=session.learner_id)
    if not rate_limit_status.allowed:
        raise RateLimitedError(retry_after_seconds=rate_limit_status.retry_after_seconds)

    if len(question) > MAX_QUESTION_LENGTH:
        raise QuestionTooLongError(max_length=MAX_QUESTION_LENGTH)

    # Langfuse v4 migration finding: this ADK-invoking call was
    # previously unwrapped -- its spans had no guaranteed flush before
    # this function (and potentially the whole Vercel Function
    # invocation) returns, unlike every other moderation-check call
    # site in this codebase (questions.py's is covered by its own
    # caller's traced_request()).
    with traced_request(learner_id=session.learner_id, session_id=session.session_id):
        allowed = await check_moderation(question, session_service=get_database_session_service())
    if not allowed:
        raise ModerationRejectedError()

    retrieved = await search_passages(db, subject_id=session.subject_id, query_text=question)
    # FR-006 (US2): a real in-process Recommendation Agent lookup when
    # the question depends on the learner's own performance -- never
    # guessed or re-derived by the Tutor Agent itself (Constitution
    # Principle I). Empty for any question that doesn't need it.
    delegation_context: list[dict] = []
    if _question_needs_performance_context(question):
        delegation_context.append(_build_recommendation_delegation(db, session))

    exchange = TutorExchange(
        session_id=session.session_id,
        question_text=question,
        delegation_context=delegation_context,
    )
    db.add(exchange)
    db.commit()
    db.refresh(exchange)

    passage_payloads = [
        {
            "passage_id": str(passage.passage_id),
            "topic_id": passage.topic_id,
            "field": passage.field.value,
            "text": passage.text,
        }
        for passage in retrieved
    ]
    stream = stream_tutor_answer(
        question=question,
        subject_id=session.subject_id,
        retrieved_passages=passage_payloads,
        delegation_context=delegation_context,
    )
    try:
        # Forces the connection (+ retry) and the first buffered chunk
        # to run now, synchronously -- everything up to `stream_tutor_
        # answer`'s first `yield` executes eagerly on this `anext()`
        # call. A `TutorUnavailableError` here means every attempt
        # failed before any content streamed back.
        first_event = await anext(stream)
    except TutorUnavailableError:
        # Leaving this exchange row with answer_text/failed_at both
        # NULL would be exactly finding H2's deadlock -- fail it now so
        # the session isn't permanently stuck behind a phantom in-flight
        # exchange (FR-015).
        exchange.failed_at = datetime.datetime.now(datetime.UTC)
        db.commit()
        raise

    return PreparedTutorMessage(
        session=session, exchange=exchange, stream=stream, first_event=first_event
    )


async def _chain_first(first: TutorStreamEvent, rest: AsyncIterator[TutorStreamEvent]):
    yield first
    async for item in rest:
        yield item


def _sse_line(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _persist_completed_exchange(
    db: Session, *, session: TutoringSession, exchange: TutorExchange, result: TutorAnswerResult
) -> None:
    exchange.answer_text = result.answer_text
    exchange.grounded = len(result.grounded_passage_ids) > 0
    exchange.retrieved_passage_ids = result.grounded_passage_ids
    db.flush()

    record_event(
        db,
        learner_id=session.learner_id,
        event_type=AssessmentEventType.TUTOR_EXCHANGE_COMPLETED,
        subject_id=session.subject_id,
        topic_id=None,
        payload={
            "exchange_id": str(exchange.exchange_id),
            "session_id": str(session.session_id),
            "retrieved_passage_ids": [str(pid) for pid in exchange.retrieved_passage_ids],
            "grounded": exchange.grounded,
            "delegation_context_summary": exchange.delegation_context or [],
        },
    )
    db.commit()


def _persist_failed_exchange(db: Session, *, exchange: TutorExchange) -> None:
    exchange.failed_at = datetime.datetime.now(datetime.UTC)
    db.commit()


async def stream_message_response(
    db: Session, *, prepared: PreparedTutorMessage
) -> AsyncIterator[str]:
    """The SSE response body (contracts/api.md's streamed wire format)
    -- one `data: {"delta": ...}` line per answer chunk, a final `data:
    {"done": true}` on success. Only ever called after `prepare_message`
    has already confirmed the Tutor Agent's stream opened successfully.

    A mid-stream failure (`TutorStreamInterruptedError`) ends the
    response with no further `data:` lines -- contracts/api.md: "no
    learner-facing response for this case beyond the connection simply
    ending, since there's no request left to respond to."
    """
    with traced_request(
        learner_id=prepared.session.learner_id, session_id=prepared.session.session_id
    ):
        try:
            async for event in _chain_first(prepared.first_event, prepared.stream):
                if isinstance(event, TutorAnswerDelta):
                    if event.text:
                        yield _sse_line({"delta": event.text})
                    continue
                _persist_completed_exchange(
                    db, session=prepared.session, exchange=prepared.exchange, result=event
                )
                # exchange_id: otherwise nothing in this response (or
                # anywhere in the frontend's DOM) ever reveals which
                # exchange this answer was -- User Story 3's inspection
                # endpoint would be undiscoverable from a real client.
                yield _sse_line({"done": True, "exchange_id": str(prepared.exchange.exchange_id)})
                return
        except TutorStreamInterruptedError:
            _persist_failed_exchange(db, exchange=prepared.exchange)
