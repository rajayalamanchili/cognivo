"""Next-question / answer / flag endpoints (contracts/api.md, User Story 2).

`next-question` takes a `learner_id` path param directly per
contracts/api.md, unlike placement's implicit demo-learner resolution --
Milestone 1 still has exactly one seeded DemoLearnerProfile, but this
endpoint's shape matches the contract as written.
"""

import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import draft_to_answer_key
from src.agents.sequencing.agent import generate_next_question
from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState
from src.models.subject import Subject
from src.observability.session import get_database_session_service
from src.observability.tracing import traced_request
from src.services.audit_log.writer import record_event
from src.services.mastery.grading import grade_answer, validate_response_shape
from src.services.quiz.session import record_quiz_answer

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

    with traced_request():
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


@router.post("/api/questions/{question_id}/answer", response_model=AnswerOut)
def answer_question(
    question_id: uuid.UUID, body: AnswerIn, db: Session = Depends(get_db)
) -> AnswerOut:
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise NotFoundError(f"unknown question_id: {question_id}")
    if _already_answered(db, question_id):
        raise ConflictError(f"question {question_id} already answered")
    try:
        validate_response_shape(question.question_type, body.response)
    except ValueError as exc:
        raise UnprocessableError(f"question {question_id}: {exc}") from exc

    correct = grade_answer(
        {"question_type": question.question_type, "answer_key": question.answer_key},
        response=body.response,
    )
    result = apply_mastery_update(
        db,
        learner_id=question.learner_id,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        correct=correct,
        question_type=question.question_type,
    )
    record_event(
        db,
        learner_id=question.learner_id,
        event_type=AssessmentEventType.ANSWER_SUBMITTED,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        question_id=question.question_id,
        payload={"response": body.response, "correct": correct},
    )
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

    return AnswerOut(
        correct=correct,
        topic_id=question.topic_id,
        prior_p_mastery=result.prior_p_mastery,
        posterior_p_mastery=result.posterior_p_mastery,
        band=result.posterior_band.value,
    )


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
