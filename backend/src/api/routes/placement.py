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

from src.agents.assessment_gen.agent import GENERATION_PROMPT_VERSION, draft_to_answer_key
from src.agents.diagnostic.agent import generate_placement_questions, grade_entry_topics
from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.grade_band import GradeBand
from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState
from src.models.prerequisite_edge import PrerequisiteEdge
from src.models.subject import Subject
from src.models.topic import Topic
from src.observability.session import get_database_session_service
from src.observability.tracing import traced_request
from src.services.audit_log.writer import record_event
from src.services.demo_learner import get_demo_learner
from src.services.mastery.grading import grade_answer, validate_response_shape
from src.services.placement.starting_grade import determine_starting_grade

router = APIRouter()


class PlacementQuestionOut(BaseModel):
    question_id: uuid.UUID
    topic_id: str
    grade: int | None = None
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

    topics = (
        db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.order_index).all()
    )
    edges = db.query(PrerequisiteEdge).filter(PrerequisiteEdge.subject_id == subject_id).all()
    # grade_entry_topics falls back to the plain is_entry_level set,
    # byte-identical to Milestone 1, for an ungraded subject (FR-009) --
    # no branching needed here (research.md Decision 2).
    placement_topics = grade_entry_topics(topics, edges)
    grade_by_topic_id = {topic.topic_id: topic.grade for topic in topics}

    placement_session_id = uuid.uuid4()

    with traced_request(learner_id=learner.learner_id, session_id=placement_session_id):
        placement_questions = await generate_placement_questions(
            placement_topics, session_service=get_database_session_service()
        )

    now = datetime.datetime.now(datetime.UTC)
    response_questions: list[PlacementQuestionOut] = []
    for placement_question in placement_questions:
        grade = grade_by_topic_id[placement_question.topic_id]
        question = GeneratedQuestion(
            learner_id=learner.learner_id,
            subject_id=subject_id,
            topic_id=placement_question.topic_id,
            grade=grade,
            placement_session_id=placement_session_id,
            difficulty=DifficultyBand.EASY,
            question_type=placement_question.question_type,
            stem=placement_question.draft.stem,
            options=placement_question.draft.options,
            answer_key=draft_to_answer_key(placement_question.draft),
            validation_status=ValidationStatus.VALID,
            shown_at=now,
            generation_prompt_version=GENERATION_PROMPT_VERSION,
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
            payload={
                "placement_session_id": str(placement_session_id),
                "difficulty": "easy",
                "grade": grade,
            },
        )

        response_questions.append(
            PlacementQuestionOut(
                question_id=question.question_id,
                topic_id=placement_question.topic_id,
                grade=grade,
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


def _declared_grades(db: Session, subject_id: str) -> list[int]:
    return [row.grade for row in db.query(GradeBand).filter(GradeBand.subject_id == subject_id).all()]


def _correct_by_grade_for_session(
    db: Session, *, subject_id: str, placement_session_id: uuid.UUID
) -> dict[int, bool]:
    """Every declared grade's grade-entry topics, mapped to whether ALL
    of them have been answered correctly so far in this placement
    session (research.md Decision 3's "question(s)", plural -- every
    grade-entry topic at a grade must be correct, not just one). A topic
    missing from this session's answers (skipped, or simply not yet
    submitted) counts as not-yet-correct, same as an explicit incorrect
    answer. Reused by both the final starting-grade assignment
    (Decision 3) and the skip endpoint's interim currently-assessed-
    level check (Decision 4) -- one canonical computation, not two.
    """
    topics = (
        db.query(Topic).filter(Topic.subject_id == subject_id).order_by(Topic.order_index).all()
    )
    edges = db.query(PrerequisiteEdge).filter(PrerequisiteEdge.subject_id == subject_id).all()
    entry_topics_by_grade: dict[int, list[str]] = {}
    for topic in grade_entry_topics(topics, edges):
        entry_topics_by_grade.setdefault(topic.grade, []).append(topic.topic_id)

    session_questions = (
        db.query(GeneratedQuestion)
        .filter(GeneratedQuestion.placement_session_id == placement_session_id)
        .all()
    )
    question_id_by_topic_id = {q.topic_id: q.question_id for q in session_questions}
    session_question_ids = [q.question_id for q in session_questions]

    answered_events = (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            AssessmentEvent.question_id.in_(session_question_ids),
        )
        .all()
    )
    correct_by_question_id = {event.question_id: event.payload["correct"] for event in answered_events}

    return {
        grade: all(
            correct_by_question_id.get(question_id_by_topic_id.get(topic_id), False)
            for topic_id in topic_ids
        )
        for grade, topic_ids in entry_topics_by_grade.items()
    }


def _assign_starting_grade_if_graded(
    db: Session,
    *,
    subject_id: str,
    learner_id: uuid.UUID,
    placement_session_id: uuid.UUID,
) -> None:
    """FR-003: assigns a learner's starting grade once, at the end of
    placement -- a no-op for an ungraded subject (FR-009, zero
    `GradeBand` rows) or if a `GradeProgress` row already exists for
    this learner/subject (idempotency guard alongside the per-question
    `_already_answered` check above)."""
    declared_grades = _declared_grades(db, subject_id)
    if not declared_grades:
        return
    if db.get(GradeProgress, (learner_id, subject_id)) is not None:
        return

    correct_by_grade = _correct_by_grade_for_session(
        db, subject_id=subject_id, placement_session_id=placement_session_id
    )
    starting_grade = determine_starting_grade(correct_by_grade, declared_grades)

    db.add(
        GradeProgress(learner_id=learner_id, subject_id=subject_id, unlocked_grade=starting_grade)
    )
    record_event(
        db,
        learner_id=learner_id,
        event_type=AssessmentEventType.GRADE_ASSIGNED,
        subject_id=subject_id,
        topic_id=None,
        payload={
            "starting_grade": starting_grade,
            "placement_session_id": str(placement_session_id),
            "correct_by_grade": {
                str(grade): correct for grade, correct in correct_by_grade.items()
            },
        },
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
            if result.grade_unlocked is not None:
                topic = db.get(Topic, (question.subject_id, question.topic_id))
                record_event(
                    db,
                    learner_id=question.learner_id,
                    event_type=AssessmentEventType.GRADE_UNLOCKED,
                    subject_id=question.subject_id,
                    topic_id=question.topic_id,
                    question_id=question.question_id,
                    payload={
                        "previous_unlocked_grade": topic.grade,
                        "new_unlocked_grade": result.grade_unlocked,
                        "triggering_topic_id": question.topic_id,
                    },
                )

    _assign_starting_grade_if_graded(
        db,
        subject_id=subject_id,
        learner_id=learner_id,
        placement_session_id=placement_session_id,
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


class SkipRequest(BaseModel):
    question_id: uuid.UUID


class SkipResponse(BaseModel):
    replacement_question: PlacementQuestionOut | None = None


@router.post("/api/placement/{placement_session_id}/skip", response_model=SkipResponse)
async def skip_placement_question(
    placement_session_id: uuid.UUID,
    body: SkipRequest,
    db: Session = Depends(get_db),
) -> SkipResponse:
    """FR-006/FR-007/FR-008, research.md Decision 4/6 (contracts/api.md).

    Skipping never mutates mastery/grade state -- it only decides
    whether the skip is currently eligible and, if so, which topic a
    replacement question is drawn from. The skipped question is simply
    never included in the eventual `submit_placement` `answers` array,
    which is what actually satisfies FR-007 (Decision 6) -- this
    endpoint's own responsibility is narrower: validate the skip and
    hand back a replacement.
    """
    question = db.get(GeneratedQuestion, body.question_id)
    if question is None or question.placement_session_id != placement_session_id:
        raise NotFoundError(
            f"question {body.question_id!r} does not belong to placement session "
            f"{placement_session_id!r}"
        )

    if _already_answered(db, question.question_id):
        raise ConflictError(f"question {question.question_id} has already been answered")

    declared_grades = _declared_grades(db, question.subject_id)
    if not declared_grades:
        raise UnprocessableError(
            f"subject {question.subject_id!r} is ungraded -- skip is not available"
        )

    correct_by_grade = _correct_by_grade_for_session(
        db, subject_id=question.subject_id, placement_session_id=placement_session_id
    )
    interim_level = determine_starting_grade(correct_by_grade, declared_grades)
    if question.grade is None or question.grade <= interim_level:
        raise UnprocessableError(
            f"question {question.question_id} (grade {question.grade}) is not above the "
            f"learner's current assessed level ({interim_level}) -- not eligible to skip"
        )

    used_topic_ids = {
        row.topic_id
        for row in db.query(GeneratedQuestion)
        .filter(GeneratedQuestion.placement_session_id == placement_session_id)
        .all()
    }
    replacement_topic = (
        db.query(Topic)
        .filter(
            Topic.subject_id == question.subject_id,
            Topic.grade.isnot(None),
            Topic.grade <= interim_level,
            Topic.topic_id.notin_(used_topic_ids),
        )
        .order_by(Topic.order_index)
        .first()
    )

    replacement_out: PlacementQuestionOut | None = None
    replacement_question_id: uuid.UUID | None = None
    replacement_grade: int | None = None

    if replacement_topic is not None:
        with traced_request(learner_id=question.learner_id, session_id=placement_session_id):
            [placement_question] = await generate_placement_questions(
                [replacement_topic], session_service=get_database_session_service()
            )

        now = datetime.datetime.now(datetime.UTC)
        replacement_grade = replacement_topic.grade
        replacement_row = GeneratedQuestion(
            learner_id=question.learner_id,
            subject_id=question.subject_id,
            topic_id=placement_question.topic_id,
            grade=replacement_grade,
            placement_session_id=placement_session_id,
            difficulty=DifficultyBand.EASY,
            question_type=placement_question.question_type,
            stem=placement_question.draft.stem,
            options=placement_question.draft.options,
            answer_key=draft_to_answer_key(placement_question.draft),
            validation_status=ValidationStatus.VALID,
            shown_at=now,
            generation_prompt_version=GENERATION_PROMPT_VERSION,
        )
        db.add(replacement_row)
        db.flush()
        replacement_question_id = replacement_row.question_id

        record_event(
            db,
            learner_id=question.learner_id,
            event_type=AssessmentEventType.PLACEMENT_QUESTION_SHOWN,
            subject_id=question.subject_id,
            topic_id=replacement_topic.topic_id,
            question_id=replacement_row.question_id,
            payload={
                "placement_session_id": str(placement_session_id),
                "difficulty": "easy",
                "grade": replacement_grade,
            },
        )

        replacement_out = PlacementQuestionOut(
            question_id=replacement_row.question_id,
            topic_id=placement_question.topic_id,
            grade=replacement_grade,
            difficulty="easy",
            question_type=placement_question.question_type.value,
            stem=placement_question.draft.stem,
            options=placement_question.draft.options,
        )

    record_event(
        db,
        learner_id=question.learner_id,
        event_type=AssessmentEventType.PLACEMENT_QUESTION_SKIPPED,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        payload={
            "skipped_question_id": str(question.question_id),
            "skipped_topic_id": question.topic_id,
            "skipped_grade": question.grade,
            "replacement_question_id": (
                str(replacement_question_id) if replacement_question_id else None
            ),
            "replacement_topic_id": replacement_topic.topic_id if replacement_topic else None,
            "replacement_grade": replacement_grade,
            "placement_session_id": str(placement_session_id),
        },
    )

    db.commit()
    return SkipResponse(replacement_question=replacement_out)
