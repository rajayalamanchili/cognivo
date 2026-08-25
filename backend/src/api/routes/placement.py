"""Placement endpoints (contracts/api.md, User Story 1).

Neither endpoint takes a `learner_id` -- Milestone 1 has exactly one
seeded `LearnerProfile` (spec.md Assumptions: solo-learner flow, no
auth/session), resolved via `services/demo_learner.get_demo_learner`.
"""

import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import draft_to_answer_key
from src.agents.diagnostic.agent import generate_placement_questions
from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState
from src.models.subject import Subject
from src.models.topic import Topic
from src.observability.session import get_database_session_service
from src.observability.tracing import traced_request
from src.services.audit_log.writer import record_event
from src.services.demo_learner import get_demo_learner
from src.services.mastery.grading import grade_answer, validate_response_shape

router = APIRouter()


class PlacementQuestionOut(BaseModel):
    question_id: uuid.UUID
    topic_id: str
    difficulty: str
    question_type: str
    stem: str
    options: list[str] | None = None


class PlacementStartResponse(BaseModel):
    placement_session_id: uuid.UUID
    questions: list[PlacementQuestionOut]


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


@router.post("/api/subjects/{subject_id}/placement/start", response_model=PlacementStartResponse)
async def start_placement(subject_id: str, db: Session = Depends(get_db)) -> PlacementStartResponse:
    _get_validated_subject(db, subject_id)
    learner = get_demo_learner(db)

    entry_level_topics = (
        db.query(Topic)
        .filter(Topic.subject_id == subject_id, Topic.is_entry_level.is_(True))
        .order_by(Topic.order_index)
        .all()
    )

    placement_session_id = uuid.uuid4()

    with traced_request(learner_id=learner.learner_id, session_id=placement_session_id):
        placement_questions = await generate_placement_questions(
            entry_level_topics, session_service=get_database_session_service()
        )

    now = datetime.datetime.now(datetime.UTC)
    response_questions: list[PlacementQuestionOut] = []
    for placement_question in placement_questions:
        question = GeneratedQuestion(
            learner_id=learner.learner_id,
            subject_id=subject_id,
            topic_id=placement_question.topic_id,
            difficulty=DifficultyBand.EASY,
            question_type=placement_question.question_type,
            stem=placement_question.draft.stem,
            options=placement_question.draft.options,
            answer_key=draft_to_answer_key(placement_question.draft),
            validation_status=ValidationStatus.VALID,
            shown_at=now,
        )
        db.add(question)
        db.flush()

        record_event(
            db,
            learner_id=learner.learner_id,
            event_type=AssessmentEventType.PLACEMENT_QUESTION_SHOWN,
            subject_id=subject_id,
            topic_id=placement_question.topic_id,
            question_id=question.question_id,
            payload={"placement_session_id": str(placement_session_id), "difficulty": "easy"},
        )

        response_questions.append(
            PlacementQuestionOut(
                question_id=question.question_id,
                topic_id=placement_question.topic_id,
                difficulty="easy",
                question_type=placement_question.question_type.value,
                stem=placement_question.draft.stem,
                options=placement_question.draft.options,
            )
        )

    db.commit()
    return PlacementStartResponse(
        placement_session_id=placement_session_id, questions=response_questions
    )


class PlacementAnswerIn(BaseModel):
    question_id: uuid.UUID
    response: Any


class PlacementSubmitRequest(BaseModel):
    answers: list[PlacementAnswerIn]


class MasteryStateOut(BaseModel):
    topic_id: str
    status: str
    p_mastery: float | None = None
    band: str | None = None


class PlacementSubmitResponse(BaseModel):
    mastery_state: list[MasteryStateOut]


def _validate_response_shape(question: GeneratedQuestion, response: Any) -> None:
    try:
        validate_response_shape(question.question_type, response)
    except ValueError as exc:
        raise UnprocessableError(f"question {question.question_id}: {exc}") from exc


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


@router.post("/api/placement/{placement_session_id}/submit", response_model=PlacementSubmitResponse)
async def submit_placement(
    placement_session_id: uuid.UUID,
    body: PlacementSubmitRequest,
    db: Session = Depends(get_db),
) -> PlacementSubmitResponse:
    if not body.answers:
        raise UnprocessableError("answers must be a non-empty list")

    questions: list[GeneratedQuestion] = []
    for answer in body.answers:
        question = db.get(GeneratedQuestion, answer.question_id)
        if question is None:
            raise UnprocessableError(f"unknown question_id: {answer.question_id}")
        _validate_response_shape(question, answer.response)
        if _already_answered(db, question.question_id):
            raise ConflictError(
                f"placement session already submitted (question {question.question_id} "
                "already answered)"
            )
        questions.append(question)

    subject_id = questions[0].subject_id
    learner_id = questions[0].learner_id
    if any(q.subject_id != subject_id or q.learner_id != learner_id for q in questions):
        raise UnprocessableError("answers span more than one subject/learner")

    with traced_request():
        for question, answer in zip(questions, body.answers, strict=True):
            correct = grade_answer(
                {
                    "question_type": question.question_type,
                    "answer_key": question.answer_key,
                },
                response=answer.response,
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
                payload={
                    "response": answer.response,
                    "correct": correct,
                    "placement_session_id": str(placement_session_id),
                },
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

    all_topics = (
        db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.order_index).all()
    )
    mastery_rows = {
        state.topic_id: state
        for state in db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .all()
    }

    mastery_state_out: list[MasteryStateOut] = []
    for topic in all_topics:
        state = mastery_rows.get(topic.topic_id)
        if state is None:
            mastery_state_out.append(MasteryStateOut(topic_id=topic.topic_id, status="unknown"))
        else:
            mastery_state_out.append(
                MasteryStateOut(
                    topic_id=topic.topic_id,
                    status="scored",
                    p_mastery=state.p_mastery,
                    band=state.band.value,
                )
            )

    db.commit()
    return PlacementSubmitResponse(mastery_state=mastery_state_out)
