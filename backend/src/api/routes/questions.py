"""Next-question / answer / flag endpoints (contracts/api.md, User Story 2).

`next-question` takes a `learner_id` path param directly per
contracts/api.md, unlike placement's implicit demo-learner resolution --
Milestone 1 still has exactly one seeded demo LearnerProfile, but this
endpoint's shape matches the contract as written.
"""

import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import draft_to_answer_key
from src.agents.sequencing.agent import generate_next_question
from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.api.errors import (
    ConflictError,
    ModerationRejectedError,
    NotFoundError,
    RateLimitedError,
    TooLongError,
    UnprocessableError,
)
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuestionType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState
from src.models.subject import Subject
from src.observability.session import get_database_session_service
from src.observability.tracing import traced_request
from src.services.audit_log.writer import record_event
from src.services.auth.dependencies import optional_session_claims
from src.services.auth.tokens import SessionClaims
from src.services.grading_client import guardrails
from src.services.grading_client.client import (
    SCORE_THRESHOLD,
    GradingResult,
    grade_free_text_answer,
)
from src.services.grading_client.moderation import check_moderation
from src.services.mastery.grading import grade_answer, validate_response_shape
from src.services.quiz.session import record_quiz_answer
from src.services.quiz_assignment.assignment import assert_guardian_owns_assignment_session

router = APIRouter()


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


class NextQuestionOut(BaseModel):
    question_id: uuid.UUID
    topic_id: str
    difficulty: str
    question_type: str
    stem: str
    options: list[str] | None = None


@router.get("/api/learners/{learner_id}/next-question", response_model=NextQuestionOut)
async def get_next_question(
    learner_id: uuid.UUID, subject_id: str, db: Session = Depends(get_db)
) -> NextQuestionOut:
    _get_validated_subject(db, subject_id)

    has_placement_data = (
        db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .first()
        is not None
    )
    if not has_placement_data:
        raise NotFoundError(
            f"learner {learner_id} has no placement data for subject {subject_id!r} yet -- "
            "complete placement first"
        )

    with traced_request(learner_id=learner_id):
        result = await generate_next_question(
            db,
            learner_id=learner_id,
            subject_id=subject_id,
            session_service=get_database_session_service(),
        )

    now = datetime.datetime.now(datetime.UTC)
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=result.selection.topic_id,
        difficulty=result.selection.difficulty,
        question_type=result.question_type,
        stem=result.draft.stem,
        options=result.draft.options,
        answer_key=draft_to_answer_key(result.draft),
        validation_status=ValidationStatus.VALID,
        shown_at=now,
    )
    db.add(question)
    db.flush()

    record_event(
        db,
        learner_id=learner_id,
        event_type=AssessmentEventType.NEXT_TOPIC_SELECTED,
        subject_id=subject_id,
        topic_id=result.selection.topic_id,
        question_id=question.question_id,
        payload={
            "candidate_topics_considered": [
                {"topic_id": c.topic_id, "band": c.band, "p_mastery": c.p_mastery}
                for c in result.selection.candidates_considered
            ],
            "chosen_topic": result.selection.topic_id,
            "chosen_topic_band": result.selection.band,
            "chosen_topic_p_mastery": result.selection.p_mastery,
            "is_fallback": result.selection.is_fallback,
        },
    )

    db.commit()
    return NextQuestionOut(
        question_id=question.question_id,
        topic_id=result.selection.topic_id,
        difficulty=result.selection.difficulty.value,
        question_type=result.question_type.value,
        stem=result.draft.stem,
        options=result.draft.options,
    )


class AnswerIn(BaseModel):
    response: Any


class AnswerOut(BaseModel):
    correct: bool
    topic_id: str
    prior_p_mastery: float | None
    posterior_p_mastery: float
    band: str
    graduated_score: float | None = None
    criteria_met: list[str] | None = None
    criteria_missed: list[str] | None = None
    grading_logic_version: str | None = None


def _already_answered(db: Session, question_id: uuid.UUID) -> bool:
    return (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.question_id == question_id,
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
        )
        .first()
        is not None
    )


def _reject_free_text(
    db: Session, *, question: GeneratedQuestion, reason: str, response_text: str
) -> None:
    """Logs a `free_text_submission_rejected` event and commits it
    immediately (data-model.md) -- the caller raises the matching
    HTTP-error exception right after this returns, so this write must
    already be durable by then. Never paired with an `ANSWER_SUBMITTED`
    event for the same submission (a rejected submission is never
    graded, contracts/api.md)."""
    record_event(
        db,
        learner_id=question.learner_id,
        event_type=AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        question_id=question.question_id,
        payload={
            "reason": reason,
            "submitted_text": response_text[: guardrails.MAX_ANSWER_LENGTH],
            "length": len(response_text),
        },
    )
    db.commit()


async def _grade_free_text_submission(
    db: Session, *, question: GeneratedQuestion, response_text: str
) -> GradingResult:
    """Runs the four pre-grading guardrails in contracts/api.md's locked
    order -- length (cheapest) -> rate limit (one DB query) -> moderation
    (one LLM call) -> grading (the A2A call) -- short-circuiting on the
    first rejection."""
    if not guardrails.check_length(response_text):
        _reject_free_text(db, question=question, reason="too_long", response_text=response_text)
        raise TooLongError(max_length=guardrails.MAX_ANSWER_LENGTH)

    rate_limit_status = guardrails.check_rate_limit(db, learner_id=question.learner_id)
    if not rate_limit_status.allowed:
        _reject_free_text(db, question=question, reason="rate_limited", response_text=response_text)
        raise RateLimitedError(retry_after_seconds=rate_limit_status.retry_after_seconds)

    allowed = await check_moderation(response_text, session_service=get_database_session_service())
    if not allowed:
        _reject_free_text(db, question=question, reason="moderation", response_text=response_text)
        raise ModerationRejectedError()

    return await grade_free_text_answer(
        question_stem=question.stem,
        rubric_criteria=question.answer_key["criteria"],
        learner_answer=response_text,
        question_id=question.question_id,
        learner_id=question.learner_id,
    )


@router.post("/api/questions/{question_id}/answer", response_model=AnswerOut)
async def answer_question(
    question_id: uuid.UUID,
    body: AnswerIn,
    db: Session = Depends(get_db),
    claims: SessionClaims | None = Depends(optional_session_claims),
) -> JSONResponse:
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise NotFoundError(f"unknown question_id: {question_id}")
    # spec 011, research.md §2: a no-op unless this question's quiz
    # session is assignment-linked -- the non-quiz and non-assigned-quiz
    # answer paths are completely unaffected.
    if question.quiz_session_id is not None:
        assert_guardian_owns_assignment_session(
            db, quiz_session_id=question.quiz_session_id, claims=claims
        )
    if _already_answered(db, question_id):
        raise ConflictError(f"question {question_id} already answered")
    try:
        validate_response_shape(question.question_type, body.response)
    except ValueError as exc:
        raise UnprocessableError(f"question {question_id}: {exc}") from exc

    grading_result: GradingResult | None = None
    if question.question_type == QuestionType.FREE_TEXT:
        with traced_request(learner_id=question.learner_id, session_id=question.quiz_session_id):
            grading_result = await _grade_free_text_submission(
                db, question=question, response_text=body.response
            )
        correct = grading_result.correct
        answer_payload = {
            "response": body.response,
            "correct": correct,
            "graduated_score": grading_result.graduated_score,
            "threshold_used": SCORE_THRESHOLD,
            "criteria_met": grading_result.criteria_met,
            "criteria_missed": grading_result.criteria_missed,
            "grading_logic_version": grading_result.grading_logic_version,
        }
    else:
        correct = grade_answer(
            {"question_type": question.question_type, "answer_key": question.answer_key},
            response=body.response,
        )
        answer_payload = {"response": body.response, "correct": correct}

    result = apply_mastery_update(
        db,
        learner_id=question.learner_id,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        correct=correct,
        question_type=question.question_type,
    )
    try:
        record_event(
            db,
            learner_id=question.learner_id,
            event_type=AssessmentEventType.ANSWER_SUBMITTED,
            subject_id=question.subject_id,
            topic_id=question.topic_id,
            question_id=question.question_id,
            payload=answer_payload,
        )
    except IntegrityError as exc:
        # `_already_answered` above is check-then-act and can't close
        # the race on its own: for free-text answers, moderation + the
        # Grading Agent A2A call (with retries) can put several seconds
        # between that check and this write, wide enough for two
        # concurrent submissions of the same question to both pass it.
        # `ix_assessment_events_answer_submitted_question_id` (migration
        # e04658523ea2) is the actual arbiter -- one of the two loses
        # here, and its whole transaction (including the mastery update
        # above) rolls back rather than double-recording (PR #18 review).
        db.rollback()
        raise ConflictError(f"question {question_id}: already answered") from exc
    record_event(
        db,
        learner_id=question.learner_id,
        event_type=AssessmentEventType.MASTERY_UPDATED,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        question_id=question.question_id,
        payload={
            "prior_p_mastery": result.prior_p_mastery,
            "posterior_p_mastery": result.posterior_p_mastery,
            "answer_correct": correct,
            "bkt_params_used": result.bkt_params_used,
        },
    )

    # Quiz-aware branch (spec 005, research.md §4): every question is
    # graded and mastery-updated via the exact same, unmodified logic
    # above regardless of whether it's quiz-linked -- this only adds
    # quiz-specific bookkeeping (FR-009's logging, FR-005's completion
    # detection) on top, never a second grading/mastery-update path.
    if question.quiz_session_id is not None:
        record_quiz_answer(db, question=question, correct=correct)

    db.commit()

    # A plain dict via JSONResponse, not `AnswerOut(...)` -- `prior_p_mastery`
    # is legitimately `None` on a learner's first observation for a topic
    # and must stay present as `null` (contracts/api.md), whereas the four
    # grading fields below must be *absent* (not merely `null`) for
    # MC/numeric answers to match the pre-existing response-shape contract
    # test. A single `response_model_exclude_none` can't apply differently
    # per field, so this builds the body explicitly instead.
    answer_body: dict[str, Any] = {
        "correct": correct,
        "topic_id": question.topic_id,
        "prior_p_mastery": result.prior_p_mastery,
        "posterior_p_mastery": result.posterior_p_mastery,
        "band": result.posterior_band.value,
    }
    if grading_result is not None:
        answer_body.update(
            graduated_score=grading_result.graduated_score,
            criteria_met=grading_result.criteria_met,
            criteria_missed=grading_result.criteria_missed,
            grading_logic_version=grading_result.grading_logic_version,
        )
    return JSONResponse(answer_body)


class FlagIn(BaseModel):
    flagged_by: uuid.UUID
    reason: str


class FlagOut(BaseModel):
    question_id: uuid.UUID
    validation_status: str


@router.post("/api/questions/{question_id}/flag", response_model=FlagOut)
def flag_question(question_id: uuid.UUID, body: FlagIn, db: Session = Depends(get_db)) -> FlagOut:
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise NotFoundError(f"unknown question_id: {question_id}")

    # FR-011: MUST NOT be deleted -- the record persists for the review
    # workflow (roadmap.md Milestone 7). Set validation_status=flagged so
    # future selection queries can filter it out (data-model.md).
    question.validation_status = ValidationStatus.FLAGGED
    question.flagged_by = body.flagged_by
    question.flagged_reason = body.reason
    db.flush()

    record_event(
        db,
        learner_id=body.flagged_by,
        event_type=AssessmentEventType.QUESTION_FLAGGED,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        question_id=question.question_id,
        payload={"reason": body.reason},
    )
    db.commit()

    return FlagOut(question_id=question.question_id, validation_status="flagged")
