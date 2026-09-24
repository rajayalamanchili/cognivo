"""Next-question / answer / flag endpoints (contracts/api.md, User Story 2).

`next-question` takes a `learner_id` path param directly per
contracts/api.md, unlike placement's implicit demo-learner resolution --
Milestone 1 still has exactly one seeded demo LearnerProfile, but this
endpoint's shape matches the contract as written.
"""

import datetime
import functools
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import GENERATION_PROMPT_VERSION, draft_to_answer_key
from src.agents.sequencing.agent import generate_next_question
from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.api.errors import (
    AlreadyAnsweredError,
    ConflictError,
    ModerationRejectedError,
    NotFoundError,
    RateLimitedError,
    StepCountMismatchError,
    TooLongError,
    UnprocessableError,
)
from src.db import get_db
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, QuestionType, QuizSessionStatus, ValidationStatus
from src.models.generated_question import GeneratedQuestion
from src.models.mastery_state import MasteryState
from src.models.practice_session import PracticeSession
from src.models.quiz_session import QuizSession
from src.models.subject import Subject
from src.models.topic import Topic
from src.observability.session import get_database_session_service
from src.observability.tracing import record_cache_hit_trace, traced_request
from src.services.audit_log.writer import record_event
from src.services.auth.dependencies import optional_session_claims
from src.services.auth.tokens import SessionClaims
from src.services.cache_common.outcome import CacheOutcome
from src.services.grading_cache.cache import get_or_grade_answer
from src.services.grading_cache.equivalence import matches_cached_criteria_pattern
from src.services.grading_client import guardrails
from src.services.grading_client.client import (
    SCORE_THRESHOLD,
    GradingResult,
    StepwiseGradingResult,
    grade_free_text_answer,
    grade_stepwise_answer,
)
from src.services.grading_client.moderation import check_moderation
from src.services.mastery.grading import grade_answer, validate_response_shape
from src.services.mediation.grade import resolve_unlocked_grade
from src.services.mediation.read_aloud import resolve_read_aloud_eligible
from src.services.quiz.session import check_and_expire_if_needed, record_quiz_answer
from src.services.quiz_assignment.assignment import assert_quiz_session_access

router = APIRouter()


def _reject_if_timed_session_ended(db: Session, *, question: GeneratedQuestion) -> None:
    """Spec 022 FR-003/FR-006, research.md §1: "an answer submitted
    after expiry is rejected, not silently scored" -- rejects (409) an
    answer for a timed quiz/practice session that has expired or been
    manually ended. A no-op for an untimed quiz/a question with no
    session at all, same as before this feature.

    Called both before grading starts (`answer_question`'s original
    check) and, for `free_text`/`multi_step`, again right after (PR
    feedback): those two question types' grading is an LLM-bound A2A
    call wide enough (this file's own comment near the `IntegrityError`
    handler below: "several seconds... with retries") for the session
    to expire or be manually ended on a concurrent request while
    grading is still in flight -- without this second call, the answer
    would still get scored and recorded for a session that had already
    ended by the time grading finished."""
    if question.quiz_session_id is not None:
        quiz = db.get(QuizSession, question.quiz_session_id)
        if quiz.time_limit_seconds is not None:
            # Always commits internally (and releases its row lock)
            # before returning, so this transition survives even though
            # the ConflictError below aborts the rest of this request.
            check_and_expire_if_needed(db, session=quiz, session_type="quiz")
            if quiz.status != QuizSessionStatus.IN_PROGRESS:
                raise ConflictError(
                    f"quiz {question.quiz_session_id}: session has ended "
                    f"(status={quiz.status.value})"
                )
    if question.practice_session_id is not None:
        # Every `PracticeSession` is timed by construction (FR-008), so
        # no `time_limit_seconds is not None` guard is needed here.
        practice_session = db.get(PracticeSession, question.practice_session_id)
        check_and_expire_if_needed(db, session=practice_session, session_type="practice")
        if practice_session.status != QuizSessionStatus.IN_PROGRESS:
            raise ConflictError(
                f"practice session {question.practice_session_id}: session has ended "
                f"(status={practice_session.status.value})"
            )


def _get_validated_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None or subject.validated_at is None:
        raise NotFoundError(f"unknown or unvalidated subject_id: {subject_id!r}")
    return subject


def time_spent_seconds(shown_at: datetime.datetime | None) -> int | None:
    """Spec 022 FR-011: server-derived answer duration from a timestamp
    already on the row (never a client-reported duration, research.md
    §6) -- shared by this route's own `answer_question` and
    `api/routes/placement.py`'s `submit_placement`, the two other places
    that formula used to be copy-pasted."""
    if shown_at is None:
        return None
    return round((datetime.datetime.now(datetime.UTC) - shown_at).total_seconds())


def has_placement_data(db: Session, *, learner_id: uuid.UUID, subject_id: str) -> bool:
    return (
        db.query(MasteryState)
        .filter(MasteryState.learner_id == learner_id, MasteryState.subject_id == subject_id)
        .first()
        is not None
    )


class NextQuestionOut(BaseModel):
    question_id: uuid.UUID
    topic_id: str
    difficulty: str
    question_type: str
    stem: str
    options: list[str] | None = None
    image_url: str | None = None
    image_alt_text: str | None = None
    steps: list[str] | None = None
    read_aloud_eligible: bool = False
    unlocked_grade: int | None = None


async def generate_and_persist_next_question(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    practice_session_id: uuid.UUID | None = None,
):
    """Generates a question via the Sequencing Agent and persists it,
    recording `next_topic_selected` -- shared by ordinary untimed
    practice (`get_next_question` below) and timed practice
    (`api/routes/practice_sessions.py`, spec 022); `practice_session_id`
    tagging is the only difference between the two callers. Does not
    commit -- same convention as `services/quiz/session.py`'s
    `persist_quiz_question`. Returns `(question, result)`; `result`
    carries `.selection`/`.draft`/`.question_type`/`.image_url`/etc.
    for the caller's own response model."""
    with traced_request(learner_id=learner_id):
        result = await generate_next_question(
            db,
            learner_id=learner_id,
            subject_id=subject_id,
            session_service=get_database_session_service(),
        )
        if result.cache_outcome.hit:
            record_cache_hit_trace(
                name="question_generation_cache_hit",
                cache_type="question_generation",
                cache_entry_id=result.cache_outcome.cache_entry_id,
                prompt_version=GENERATION_PROMPT_VERSION,
                learner_id=learner_id,
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
        image_url=result.image_url,
        image_alt_text=result.image_alt_text,
        answer_key=draft_to_answer_key(result.draft),
        validation_status=ValidationStatus.VALID,
        shown_at=now,
        generation_prompt_version=GENERATION_PROMPT_VERSION,
        practice_session_id=practice_session_id,
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
            "served_from_cache": result.cache_outcome.hit,
            "cache_miss_reason": result.cache_outcome.reason,
        },
    )
    return question, result


def build_next_question_out(
    db: Session, *, question: GeneratedQuestion, result, learner_id: uuid.UUID, subject_id: str
) -> NextQuestionOut:
    """Builds the shared `NextQuestionOut` response shape from a
    `generate_and_persist_next_question` result -- reused by this
    route's own `get_next_question` and by `api/routes/
    practice_sessions.py`'s two timed-practice next-question routes
    (spec 022), so a future field addition only needs to change once."""
    return NextQuestionOut(
        question_id=question.question_id,
        topic_id=result.selection.topic_id,
        difficulty=result.selection.difficulty.value,
        question_type=result.question_type.value,
        stem=result.draft.stem,
        options=result.draft.options,
        image_url=result.image_url,
        image_alt_text=result.image_alt_text,
        # Step prompts only, never the per-step rubric criteria (spec 018
        # FR-002) -- the answer key must not leak to the client, same
        # discipline as every other question_type's answer_key.
        steps=(
            [step.step_prompt for step in result.draft.steps]
            if result.question_type == QuestionType.MULTI_STEP
            else None
        ),
        read_aloud_eligible=resolve_read_aloud_eligible(
            db, learner_id=learner_id, subject_id=subject_id
        ),
        unlocked_grade=resolve_unlocked_grade(db, learner_id=learner_id, subject_id=subject_id),
    )


@router.get("/api/learners/{learner_id}/next-question", response_model=NextQuestionOut)
async def get_next_question(
    learner_id: uuid.UUID, subject_id: str, db: Session = Depends(get_db)
) -> NextQuestionOut:
    _get_validated_subject(db, subject_id)

    if not has_placement_data(db, learner_id=learner_id, subject_id=subject_id):
        raise NotFoundError(
            f"learner {learner_id} has no placement data for subject {subject_id!r} yet -- "
            "complete placement first"
        )

    question, result = await generate_and_persist_next_question(
        db, learner_id=learner_id, subject_id=subject_id
    )
    db.commit()
    return build_next_question_out(
        db, question=question, result=result, learner_id=learner_id, subject_id=subject_id
    )


class AnswerIn(BaseModel):
    response: Any
    read_aloud_used: bool = False


class StepResultOut(BaseModel):
    step_index: int
    correct: bool
    criteria_met: list[str]
    criteria_missed: list[str]


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
    first_diverging_step_index: int | None = None
    step_results: list[StepResultOut] | None = None


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
    graded, contracts/api.md).

    Reused for `multi_step` submissions too (spec 018 contracts/api.md:
    length/rate-limit/moderation rejection is "identical in shape" to
    free-text's) -- no separate event type exists for it, `response_text`
    is simply the submission's concatenated step text in that case.
    """
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
) -> tuple[GradingResult, CacheOutcome]:
    """Runs the four pre-grading guardrails in contracts/api.md's locked
    order -- length (cheapest) -> rate limit (one DB query) -> moderation
    (one LLM call) -> grading (cache-checked, then the A2A call on a
    miss) -- short-circuiting on the first rejection."""
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

    return await get_or_grade_answer(
        db,
        question_stem=question.stem,
        rubric_criteria=question.answer_key["criteria"],
        learner_answer=response_text,
        question_id=question.question_id,
        learner_id=question.learner_id,
        # GRADING_LOGIC_VERSION is a code constant living in the
        # separately-deployed grading-agent/ service (A2A boundary,
        # Constitution Principle VI) -- not importable here. This env
        # var must be kept in sync with it manually, mirroring
        # GRADING_AGENT_URL/GRADING_AGENT_SHARED_SECRET's existing
        # cross-deployment sync pattern (spec 015 research.md §3).
        # Optional, not required (unlike those two): an unset/stale
        # value only ever risks a wrong cache decision (a miss that
        # could've been a hit, or FR-006 in reverse), never a request
        # failure -- the actual grading result always comes from a real
        # grade_fn() call on any miss, same fail-open spirit as FR-008.
        # Defaults to the version live at the time this feature shipped.
        grading_logic_version=os.environ.get("GRADING_AGENT_LOGIC_VERSION", "v3"),
        grade_fn=grade_free_text_answer,
        # FR-003: an embedding-close candidate is never served on
        # distance alone -- this rubric-criteria re-classification
        # (equivalence.py) is the actual gate, never touching the
        # original learner's raw answer text (FR-009).
        verify_fn=functools.partial(
            matches_cached_criteria_pattern, session_service=get_database_session_service()
        ),
    )


async def _grade_stepwise_submission(
    db: Session, *, question: GeneratedQuestion, response_steps: list[str]
) -> StepwiseGradingResult:
    """Multi-step counterpart to `_grade_free_text_submission` (spec 018).
    Same length/rate-limit/moderation guardrail order, run against the
    submission's concatenated step text (contracts/api.md) -- but calls
    `grade_stepwise_answer()` directly rather than `get_or_grade_answer()`,
    bypassing Milestone 13's semantic grading cache for `multi_step`
    submissions in v1 (research.md §6, plan.md's Constraints).

    FR-012's step-count check runs first -- cheapest (one length
    comparison against the question's own `answer_key`, no DB query
    beyond what's already loaded), before length/rate-limit/moderation/
    grading (contracts/api.md's error-state ordering)."""
    expected_step_count = len(question.answer_key["steps"])
    if len(response_steps) != expected_step_count:
        record_event(
            db,
            learner_id=question.learner_id,
            event_type=AssessmentEventType.STEP_COUNT_MISMATCH_REJECTED,
            subject_id=question.subject_id,
            topic_id=question.topic_id,
            question_id=question.question_id,
            payload={
                "expected_step_count": expected_step_count,
                "submitted_step_count": len(response_steps),
            },
        )
        db.commit()
        raise StepCountMismatchError(
            expected_step_count=expected_step_count,
            submitted_step_count=len(response_steps),
        )

    concatenated = "\n".join(response_steps)
    if not guardrails.check_length(concatenated):
        _reject_free_text(db, question=question, reason="too_long", response_text=concatenated)
        raise TooLongError(max_length=guardrails.MAX_ANSWER_LENGTH)

    rate_limit_status = guardrails.check_rate_limit(db, learner_id=question.learner_id)
    if not rate_limit_status.allowed:
        _reject_free_text(db, question=question, reason="rate_limited", response_text=concatenated)
        raise RateLimitedError(retry_after_seconds=rate_limit_status.retry_after_seconds)

    allowed = await check_moderation(concatenated, session_service=get_database_session_service())
    if not allowed:
        _reject_free_text(db, question=question, reason="moderation", response_text=concatenated)
        raise ModerationRejectedError()

    return await grade_stepwise_answer(
        question_stem=question.stem,
        steps=question.answer_key["steps"],
        learner_steps=response_steps,
        question_id=question.question_id,
        learner_id=question.learner_id,
    )


@router.post("/api/questions/{question_id}/answer", response_model=AnswerOut)
async def answer_question(
    question_id: uuid.UUID,
    body: AnswerIn,
    db: Session = Depends(get_db),
    claims: SessionClaims | None = Depends(optional_session_claims),
    x_quiz_handoff_token: str | None = Header(default=None),
) -> JSONResponse:
    question = db.get(GeneratedQuestion, question_id)
    if question is None:
        raise NotFoundError(f"unknown question_id: {question_id}")
    # spec 011, research.md §2 (extended by spec 019 with tier-aware
    # hand-off-token support): a no-op unless this question's quiz
    # session is assignment-linked -- the non-quiz and non-assigned-quiz
    # answer paths are completely unaffected.
    if question.quiz_session_id is not None:
        assert_quiz_session_access(
            db,
            quiz_session_id=question.quiz_session_id,
            claims=claims,
            handoff_token=x_quiz_handoff_token,
        )
    _reject_if_timed_session_ended(db, question=question)
    if _already_answered(db, question_id):
        raise AlreadyAnsweredError(question_id)
    try:
        validate_response_shape(question.question_type, body.response)
    except ValueError as exc:
        raise UnprocessableError(f"question {question_id}: {exc}") from exc

    grading_result: GradingResult | None = None
    stepwise_result: StepwiseGradingResult | None = None
    if question.question_type == QuestionType.FREE_TEXT:
        with traced_request(learner_id=question.learner_id, session_id=question.quiz_session_id):
            grading_result, cache_outcome = await _grade_free_text_submission(
                db, question=question, response_text=body.response
            )
            if cache_outcome.hit:
                record_cache_hit_trace(
                    name="grading_cache_hit",
                    cache_type="grading",
                    cache_entry_id=cache_outcome.cache_entry_id,
                    prompt_version=grading_result.grading_logic_version,
                    learner_id=question.learner_id,
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
            "served_from_cache": cache_outcome.hit,
            "cache_miss_reason": cache_outcome.reason,
            "read_aloud_used": body.read_aloud_used,
        }
    elif question.question_type == QuestionType.MULTI_STEP:
        with traced_request(learner_id=question.learner_id, session_id=question.quiz_session_id):
            stepwise_result = await _grade_stepwise_submission(
                db, question=question, response_steps=body.response
            )
        correct = stepwise_result.correct
        answer_payload = {
            "response": body.response,
            "correct": correct,
            "graduated_score": stepwise_result.graduated_score,
            "threshold_used": SCORE_THRESHOLD,
            "first_diverging_step_index": stepwise_result.first_diverging_step_index,
            "step_results": [
                {
                    "step_index": s.step_index,
                    "correct": s.correct,
                    "criteria_met": s.criteria_met,
                    "criteria_missed": s.criteria_missed,
                }
                for s in stepwise_result.step_results
            ],
            "grading_logic_version": stepwise_result.grading_logic_version,
            "read_aloud_used": body.read_aloud_used,
        }
    else:
        correct = grade_answer(
            {"question_type": question.question_type, "answer_key": question.answer_key},
            response=body.response,
        )
        answer_payload = {
            "response": body.response,
            "correct": correct,
            "read_aloud_used": body.read_aloud_used,
        }

    # PR feedback: re-run the same expiry/status check from before
    # grading started -- see `_reject_if_timed_session_ended`'s
    # docstring. A near-instant no-op for MC/numeric (the `else` branch
    # above awaits nothing), but free_text/multi_step's grading call
    # above can take long enough for the session to have expired or been
    # manually ended while it was in flight; this must run (and reject,
    # discarding the grading result above) before anything below scores
    # or records this answer.
    _reject_if_timed_session_ended(db, question=question)

    # Spec 022 FR-011: recorded for every answered question -- placement,
    # untimed practice, untimed quiz, timed practice, timed quiz alike,
    # no exceptions. `shown_at` is always set by the time a question can
    # be answered at all (a question must reach VALID before `shown_at`
    # may be set), so this guard is defensive only.
    spent = time_spent_seconds(question.shown_at)
    if spent is not None:
        answer_payload["time_spent_seconds"] = spent

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
        raise AlreadyAnsweredError(question_id) from exc
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
    elif stepwise_result is not None:
        answer_body.update(
            graduated_score=stepwise_result.graduated_score,
            # The per-step breakdown replaces the flat criteria fields,
            # it does not sit alongside them (contracts/api.md).
            criteria_met=None,
            criteria_missed=None,
            first_diverging_step_index=stepwise_result.first_diverging_step_index,
            step_results=[
                {
                    "step_index": s.step_index,
                    "correct": s.correct,
                    "criteria_met": s.criteria_met,
                    "criteria_missed": s.criteria_missed,
                }
                for s in stepwise_result.step_results
            ],
            grading_logic_version=stepwise_result.grading_logic_version,
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
