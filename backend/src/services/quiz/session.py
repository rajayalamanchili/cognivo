"""Quiz session orchestration (spec 005).

`next_quiz_topic` is the pure round-robin rule (research.md §2),
directly unit-testable with no DB. `start_quiz`, `generate_quiz_question`,
`compute_quiz_summary`, and `record_quiz_answer` are the DB-querying
orchestration built on top of it and on `services/quiz/difficulty.py`'s
pure rule -- mirrors `weak_area.py`'s/`agents/sequencing/agent.py`'s own
pure-rule-plus-DB-orchestration split.
"""

import datetime
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from google.adk.sessions import BaseSessionService
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import (
    GENERATION_PROMPT_VERSION,
    GeneratedQuestionDraft,
    draft_to_answer_key,
    generate_question,
)
from src.agents.diagnostic.agent import difficulty_guidance, preferred_question_type, skill_summary
from src.api.errors import UnprocessableError
from src.models.assessment_event import AssessmentEvent
from src.models.enums import (
    AssessmentEventType,
    DifficultyBand,
    QuestionType,
    QuizSessionStatus,
    ValidationStatus,
)
from src.models.generated_question import GeneratedQuestion
from src.models.practice_session import PracticeSession
from src.models.quiz_session import QuizSession
from src.models.subject import Subject
from src.models.topic import Topic
from src.observability.tracing import record_cache_hit_trace
from src.services.audit_log.writer import record_event
from src.services.cache_common.outcome import CacheOutcome
from src.services.content_artifact.image_asset import content_image_url
from src.services.dedup.checker import is_near_duplicate, recent_stems_for_topic
from src.services.question_cache.cache import get_or_generate_question
from src.services.quiz.difficulty import (
    current_difficulty_for_topic,
    next_difficulty,
    replay_topic_state,
)

DEFAULT_MAX_DEDUP_ATTEMPTS = 3

# Spec 022 FR-001/Assumptions: a small fixed preset (15/30/45/60
# minutes), not an arbitrary custom duration -- shared by both
# `POST /api/quizzes` and `POST /api/practice-sessions` (FR-001 is one
# requirement, not two independently-drifting lists).
ALLOWED_TIME_LIMIT_SECONDS = {900, 1800, 2700, 3600}


def validate_time_limit_seconds(time_limit_seconds: int | None) -> None:
    if time_limit_seconds is not None and time_limit_seconds not in ALLOWED_TIME_LIMIT_SECONDS:
        raise UnprocessableError(
            f"time_limit_seconds must be one of {sorted(ALLOWED_TIME_LIMIT_SECONDS)} or omitted"
        )


class QuizEndedEarlyError(Exception):
    """Raised when a fresh, distinct question cannot be generated for a
    topic after exhausting dedup retries (FR-008) -- the caller must
    transition `QuizSession.status` to `ended_early` rather than serve
    a near-duplicate (research.md §3)."""


class SessionNotTimedError(Exception):
    """Raised by `end_session_manually` (spec 022 FR-010) when the
    target session has no `time_limit_seconds` set -- there is nothing
    to manually end early on an untimed session (contracts/api.md's
    `404` case for quiz; every `PracticeSession` is timed by
    construction, so this never applies to practice)."""


class SessionAlreadyEndedError(Exception):
    """Raised by `end_session_manually` (spec 022 FR-010) when the
    target session is not `in_progress` (contracts/api.md's `409`
    case)."""


# Spec 022: a "timed session" is either a QuizSession or a
# PracticeSession with `time_limit_seconds` set. `session_type` picks
# which id field/audit-log label applies, since the two models share no
# common base beyond both being thin session header rows.
TimedSession = QuizSession | PracticeSession
SessionKind = Literal["quiz", "practice"]


def _timed_session_id(session: TimedSession, session_type: SessionKind) -> uuid.UUID:
    return session.quiz_session_id if session_type == "quiz" else session.practice_session_id


def _end_timed_session(
    db: Session,
    *,
    session: TimedSession,
    session_type: SessionKind,
    status: QuizSessionStatus,
    end_reason: Literal["completed", "timer_expired", "manually_ended_early", "dedup_exhausted"],
) -> None:
    """Shared transition + audit-event write for every way a timed
    session can end (spec 022 research.md §1/§3/§4): timer expiry,
    manual early-end, or (quiz only) reaching its configured question
    count -- `record_quiz_answer` below calls this for that third case
    instead of setting `status`/`completed_at` inline, so a *timed*
    quiz's completion is just as audited as its other two end reasons
    (FR-007 -- "every timed session", not just the expiry/manual-end
    ones). Never called for an untimed session -- FR-009's zero-
    behavior-change guarantee depends on that. Does not commit, same
    convention as the rest of this module."""
    now = datetime.datetime.now(datetime.UTC)
    session.status = status
    session.completed_at = now
    elapsed_seconds = round((now - session.started_at).total_seconds())
    record_event(
        db,
        learner_id=session.learner_id,
        event_type=AssessmentEventType.TIMED_SESSION_ENDED,
        subject_id=session.subject_id,
        topic_id=None,
        payload={
            "session_type": session_type,
            "session_id": str(_timed_session_id(session, session_type)),
            "time_limit_seconds": session.time_limit_seconds,
            "elapsed_seconds": elapsed_seconds,
            "end_reason": end_reason,
        },
    )
    db.flush()


def check_and_expire_if_needed(
    db: Session, *, session: TimedSession, session_type: SessionKind
) -> bool:
    """Lazy, per-request expiry check (spec 022 research.md §1) -- never
    a background timer process, per Constitution Principle IX's
    stateless-Vercel constraint. No-op (returns `False`) if the session
    is untimed or already not `in_progress`; idempotent once expired --
    a second call after the first also returns `False`, since `status`
    is no longer `in_progress` by then. Returns `True` only on the call
    that actually just transitioned the session to `ended_early`.

    Row-locks `session` before checking `status` (PR feedback: two
    concurrent requests against the same expired session could otherwise
    both observe `in_progress` and both write a competing
    `TIMED_SESSION_ENDED` event) -- skipped for the common untimed case,
    where there is nothing to race over. Always commits before
    returning, even when nothing changed, so that lock is released
    immediately rather than held for the rest of the request (PR
    feedback): every caller runs this before a possibly-slow LLM-bound
    call (next-question generation, answer grading), which would
    otherwise hold the lock across it and block a concurrent manual
    "end now"/expiry check on the same session for the whole duration."""
    if session.time_limit_seconds is None:
        return False
    db.refresh(session, with_for_update=True)
    if session.status != QuizSessionStatus.IN_PROGRESS:
        db.commit()
        return False
    expires_at = session.started_at + datetime.timedelta(seconds=session.time_limit_seconds)
    if datetime.datetime.now(datetime.UTC) < expires_at:
        db.commit()
        return False
    _end_timed_session(
        db,
        session=session,
        session_type=session_type,
        status=QuizSessionStatus.ENDED_EARLY,
        end_reason="timer_expired",
    )
    db.commit()
    return True


def session_still_in_progress(db: Session, *, session: TimedSession) -> bool:
    """Re-checks `session.status` under a fresh row lock (PR feedback).

    `check_and_expire_if_needed` deliberately commits and releases its
    own lock before a caller's slow, LLM-bound question-generation call
    runs, so that call doesn't block a concurrent manual end-now/expiry
    on the same session. That leaves a TOCTOU window open on the other
    side: a concurrent request can end the session while generation is
    in flight, and without this re-check, the generated question would
    still get persisted and returned for a session that had already
    ended by the time it was ready. Callers should call this
    immediately before persisting/returning a freshly-generated
    question, and hold the resulting lock through that write (same
    convention as `record_quiz_answer`'s own re-check before its
    completion write).

    No-op (returns `True` immediately, no lock taken) for an untimed
    session -- there's nothing to race over."""
    if session.time_limit_seconds is None:
        return True
    db.refresh(session, with_for_update=True)
    return session.status == QuizSessionStatus.IN_PROGRESS


def session_expires_at(session: TimedSession) -> str | None:
    """`expires_at = started_at + time_limit_seconds` (spec 022
    research.md §1), `None` for an untimed session -- shared by
    `api/routes/quiz.py` and `api/routes/practice_sessions.py` so the
    formula can't drift between the two copies it used to be (every
    `PracticeSession` is timed by construction, so this is never `None`
    there)."""
    if session.time_limit_seconds is None:
        return None
    return (session.started_at + datetime.timedelta(seconds=session.time_limit_seconds)).isoformat()


def end_session_manually(db: Session, *, session: TimedSession, session_type: SessionKind) -> None:
    """Manual early-end (spec 022 FR-010) -- a new capability that
    exists only for timed sessions (research.md §4: today's untimed
    quiz/practice has no learner-initiated "end now" action at all).

    Row-locks `session` before checking `status` (PR feedback), same as
    `check_and_expire_if_needed` -- without it, this could race that
    function's own lock and clobber an already-terminal session with a
    second, contradictory `TIMED_SESSION_ENDED` event (e.g. the
    countdown's auto-fired expiry request landing at the same moment as
    a manual "end now" click)."""
    if session.time_limit_seconds is None:
        raise SessionNotTimedError(f"{session_type} session has no time limit to end early")
    db.refresh(session, with_for_update=True)
    if session.status != QuizSessionStatus.IN_PROGRESS:
        raise SessionAlreadyEndedError(f"{session_type} session is already {session.status.value}")
    _end_timed_session(
        db,
        session=session,
        session_type=session_type,
        status=QuizSessionStatus.ENDED_EARLY,
        end_reason="manually_ended_early",
    )


def end_quiz_for_dedup_exhaustion(db: Session, *, quiz: QuizSession) -> None:
    """Called from `api/routes/quiz.py`'s two `QuizEndedEarlyError`
    handlers (dedup-retry exhaustion, research.md §4) -- the only
    `ended_early` trigger that isn't timer expiry or a manual "end now".
    For an untimed quiz this is unchanged (FR-009): sets `status`/
    `completed_at` inline, no audit event. For a *timed* quiz, PR
    feedback found this previously bypassed `_end_timed_session`
    entirely, so `compute_timed_session_timing` had no
    `TIMED_SESSION_ENDED` event to read and silently reported
    `elapsed_seconds`/`end_reason` as `None` for a session that had
    already ended (SC-005 miss) -- goes through it now, same as the
    other two timed end-reasons.

    Row-locks + re-checks status first, same reasoning as
    `record_quiz_answer`'s own `_end_timed_session` call: a concurrent
    manual "end now"/expiry could already have transitioned `quiz` by
    the time generation raises `QuizEndedEarlyError`, and this must not
    clobber that with a second, contradictory event."""
    if quiz.time_limit_seconds is None:
        quiz.status = QuizSessionStatus.ENDED_EARLY
        quiz.completed_at = datetime.datetime.now(datetime.UTC)
        db.flush()
        return
    db.refresh(quiz, with_for_update=True)
    if quiz.status == QuizSessionStatus.IN_PROGRESS:
        _end_timed_session(
            db,
            session=quiz,
            session_type="quiz",
            status=QuizSessionStatus.ENDED_EARLY,
            end_reason="dedup_exhausted",
        )


def next_quiz_topic(topic_ids: Sequence[str], *, questions_generated_so_far: int) -> str:
    """The topic for this quiz's next question: round-robin through
    `topic_ids` in selection order, one question per topic per cycle
    (Clarifications, 2026-08-18)."""
    return topic_ids[questions_generated_so_far % len(topic_ids)]


def start_quiz(
    db: Session,
    *,
    learner_id: uuid.UUID,
    subject_id: str,
    topic_ids: list[str],
    question_count: int,
    time_limit_seconds: int | None = None,
) -> QuizSession:
    """Persists a new `QuizSession` row (`status=in_progress`). Does not
    commit, and does not validate `topic_ids`/`question_count`/
    `time_limit_seconds` -- the caller (the API route) is responsible
    for FR-001's request-shape validation before calling this, matching
    this codebase's existing convention of validating in the route
    layer. `time_limit_seconds` defaults to `None` (untimed, spec 022
    FR-009) -- `quiz_assignment/assignment.py`'s `start_assignment_
    attempt` doesn't pass it, unaffected by this addition."""
    quiz = QuizSession(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_ids=list(topic_ids),
        question_count=question_count,
        time_limit_seconds=time_limit_seconds,
    )
    db.add(quiz)
    db.flush()
    return quiz


def _topic_answer_history(
    db: Session,
    *,
    quiz_session_id: uuid.UUID,
    topic_id: str,
    exclude_question_id: uuid.UUID | None = None,
) -> list[bool]:
    """This quiz's ordered (correct/incorrect) history for `topic_id`,
    generation order -- only questions already answered, since an
    unanswered question hasn't produced a difficulty decision yet.

    `exclude_question_id` matters when a question's own
    `ANSWER_SUBMITTED` event has already been flushed (visible to this
    same DB session) by the time this is called for that same question
    -- without excluding it explicitly, it would double-count as its
    own "prior" history. Passing `None` (the default, used when
    generating a brand-new question) is correct: there is no current
    question yet to exclude."""
    query = (
        db.query(GeneratedQuestion, AssessmentEvent)
        .join(
            AssessmentEvent,
            (AssessmentEvent.question_id == GeneratedQuestion.question_id)
            & (AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED),
        )
        .filter(
            GeneratedQuestion.quiz_session_id == quiz_session_id,
            GeneratedQuestion.topic_id == topic_id,
        )
    )
    if exclude_question_id is not None:
        query = query.filter(GeneratedQuestion.question_id != exclude_question_id)
    rows = query.order_by(GeneratedQuestion.generated_at).all()
    return [event.payload["correct"] for _question, event in rows]


@dataclass(frozen=True)
class QuizQuestionResult:
    topic_id: str
    question_type: QuestionType
    difficulty: DifficultyBand
    draft: GeneratedQuestionDraft
    image_url: str | None = None
    image_alt_text: str | None = None
    cache_outcome: CacheOutcome = field(default_factory=lambda: CacheOutcome(hit=False))


async def generate_quiz_question(
    db: Session,
    *,
    quiz: QuizSession,
    session_service: BaseSessionService,
    max_dedup_attempts: int = DEFAULT_MAX_DEDUP_ATTEMPTS,
) -> QuizQuestionResult:
    """Generates the next question for `quiz`: round-robin topic
    selection (research.md §2), streak-based difficulty (research.md
    §1), and a hard near-duplicate guarantee -- the dedup lookback is
    widened to `quiz.question_count` (not Milestone 1's 5-question
    default) so it covers this quiz's *entire* history for the topic,
    not just the last few (FR-008, research.md §3). Raises
    `QuizEndedEarlyError` instead of ever returning a near-duplicate
    once `max_dedup_attempts` is exhausted."""
    questions_generated_so_far = (
        db.query(GeneratedQuestion)
        .filter(GeneratedQuestion.quiz_session_id == quiz.quiz_session_id)
        .count()
    )
    topic_id = next_quiz_topic(
        quiz.topic_ids, questions_generated_so_far=questions_generated_so_far
    )
    topic = db.get(Topic, (quiz.subject_id, topic_id))

    history = _topic_answer_history(db, quiz_session_id=quiz.quiz_session_id, topic_id=topic_id)
    difficulty = current_difficulty_for_topic(history)
    question_type = preferred_question_type(topic)
    recent_stems = recent_stems_for_topic(
        db,
        learner_id=quiz.learner_id,
        subject_id=quiz.subject_id,
        topic_id=topic_id,
        limit=quiz.question_count,
    )

    image_url: str | None = None
    image_alt_text: str | None = None
    if topic.image_asset is not None:
        image_url = content_image_url(quiz.subject_id, topic.image_asset["filename"])
        image_alt_text = topic.image_asset["alt_text"]

    content_version = db.get(Subject, quiz.subject_id).content_version

    for _ in range(max_dedup_attempts):
        draft, cache_outcome = await get_or_generate_question(
            db,
            subject_id=quiz.subject_id,
            topic_id=topic_id,
            difficulty=difficulty,
            content_version=content_version,
            generation_prompt_version=GENERATION_PROMPT_VERSION,
            avoid_stems=recent_stems,
            generate_fn=lambda: generate_question(
                topic_display_name=topic.display_name,
                skill_summary=skill_summary(topic),
                difficulty=difficulty,
                difficulty_guidance=difficulty_guidance(topic, difficulty),
                question_type=question_type,
                session_service=session_service,
                avoid_stems=recent_stems,
                image_alt_text=image_alt_text,
            ),
        )
        if not is_near_duplicate(draft.stem, recent_stems):
            if cache_outcome.hit:
                # Spec 015 FR-013 clarification: this path records no
                # dedicated AssessmentEvent for question generation even
                # on a fresh call (only QUIZ_DIFFICULTY_ADJUSTED, post-
                # answer) -- its own per-learner GeneratedQuestion row
                # (persist_quiz_question below, unchanged by caching)
                # already satisfies the audit-log half for this path, so
                # only the Langfuse trace is recorded explicitly here.
                record_cache_hit_trace(
                    name="quiz_question_generation_cache_hit",
                    cache_type="question_generation",
                    cache_entry_id=cache_outcome.cache_entry_id,
                    prompt_version=GENERATION_PROMPT_VERSION,
                    learner_id=quiz.learner_id,
                )
            return QuizQuestionResult(
                topic_id=topic_id,
                question_type=question_type,
                difficulty=difficulty,
                draft=draft,
                image_url=image_url,
                image_alt_text=image_alt_text,
                cache_outcome=cache_outcome,
            )

    raise QuizEndedEarlyError(
        f"quiz {quiz.quiz_session_id}: could not generate a fresh question for topic "
        f"{topic_id!r} after {max_dedup_attempts} attempts"
    )


def persist_quiz_question(
    db: Session,
    *,
    quiz_session_id: uuid.UUID,
    learner_id: uuid.UUID,
    subject_id: str,
    result: QuizQuestionResult,
) -> GeneratedQuestion:
    """Builds and persists the `GeneratedQuestion` row for a freshly
    generated quiz question. Shared by `POST /api/quizzes`/`GET
    /api/quizzes/{quiz_session_id}/next-question` (spec 005) and the
    assignment-attempt start path (spec 011, `services/quiz_assignment/
    assignment.py`'s `start_assignment_attempt`) so a quiz question is
    persisted identically regardless of which route generated it
    (SC-002's parity guarantee). Does not commit -- same convention as
    `start_quiz` above."""
    now = datetime.datetime.now(datetime.UTC)
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=result.topic_id,
        difficulty=result.difficulty,
        question_type=result.question_type,
        stem=result.draft.stem,
        options=result.draft.options,
        image_url=result.image_url,
        image_alt_text=result.image_alt_text,
        answer_key=draft_to_answer_key(result.draft),
        validation_status=ValidationStatus.VALID,
        shown_at=now,
        quiz_session_id=quiz_session_id,
        generation_prompt_version=GENERATION_PROMPT_VERSION,
    )
    db.add(question)
    db.flush()
    return question


def record_quiz_answer(db: Session, *, question: GeneratedQuestion, correct: bool) -> None:
    """Called from the quiz-aware branch of `answer_question` (research.md
    §4), *after* the shared `ANSWER_SUBMITTED` event for this same
    question has already been flushed to this DB session -- both queries
    below explicitly exclude `question.question_id` so that already-
    flushed event is never double-counted as its own "prior" history.
    Logs the `quiz_difficulty_adjusted` decision (FR-009) using this
    topic's prior history only, and flips `QuizSession.status` to
    `completed` once this quiz's answered-question count reaches
    `question_count`."""
    quiz = db.get(QuizSession, question.quiz_session_id)

    prior_history = _topic_answer_history(
        db,
        quiz_session_id=quiz.quiz_session_id,
        topic_id=question.topic_id,
        exclude_question_id=question.question_id,
    )
    pre_band, pre_streak = replay_topic_state(prior_history)
    step = next_difficulty(pre_band, pre_streak, correct=correct)

    record_event(
        db,
        learner_id=quiz.learner_id,
        event_type=AssessmentEventType.QUIZ_DIFFICULTY_ADJUSTED,
        subject_id=quiz.subject_id,
        topic_id=question.topic_id,
        question_id=question.question_id,
        payload={
            "quiz_session_id": str(quiz.quiz_session_id),
            "prior_band": pre_band.value,
            "new_band": step.band.value,
            "streak_direction": "correct" if correct else "incorrect",
            "streak_length_at_decision": step.streak_length_at_decision,
            "held_at_bound": step.held_at_bound,
        },
    )

    answered_count_before = (
        db.query(AssessmentEvent)
        .join(GeneratedQuestion, GeneratedQuestion.question_id == AssessmentEvent.question_id)
        .filter(
            GeneratedQuestion.quiz_session_id == quiz.quiz_session_id,
            AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED,
            GeneratedQuestion.question_id != question.question_id,
        )
        .count()
    )
    if answered_count_before + 1 >= quiz.question_count:
        if quiz.time_limit_seconds is not None:
            # Spec 022 FR-007: a timed quiz's completion is audited the
            # same as its other two end reasons, not just set inline.
            #
            # Row-locks + re-checks status (PR feedback): this is the
            # third way `_end_timed_session` can be reached, alongside
            # `check_and_expire_if_needed`/`end_session_manually`, which
            # already guard against a concurrent transition the same
            # way. Without it, a manual "end now"/expiry racing ahead of
            # this request's own final-answer submission could already
            # have transitioned the session by the time this branch
            # runs, and unconditionally completing it here would
            # clobber that with a second, contradictory
            # `TIMED_SESSION_ENDED` event.
            db.refresh(quiz, with_for_update=True)
            if quiz.status == QuizSessionStatus.IN_PROGRESS:
                _end_timed_session(
                    db,
                    session=quiz,
                    session_type="quiz",
                    status=QuizSessionStatus.COMPLETED,
                    end_reason="completed",
                )
        else:
            quiz.status = QuizSessionStatus.COMPLETED
            quiz.completed_at = datetime.datetime.now(datetime.UTC)
            db.flush()


@dataclass(frozen=True)
class QuizScore:
    correct: int
    total: int


@dataclass(frozen=True)
class QuizSummaryEntry:
    topic_id: str
    difficulty: DifficultyBand
    correct: int
    total: int


@dataclass(frozen=True)
class QuizSummary:
    score: QuizScore
    breakdown: list[QuizSummaryEntry] = field(default_factory=list)


def compute_quiz_summary(db: Session, *, quiz_session_id: uuid.UUID) -> QuizSummary:
    """Score and a per-(topic, difficulty) breakdown, computed at read
    time from this quiz's answered `GeneratedQuestion`/`AssessmentEvent`
    rows -- no separate summary table (data-model.md). Groups by
    (topic_id, difficulty) in the order those combinations were first
    encountered, correct even while the quiz is still `in_progress`
    (a partial tally, not an error, FR-006/contracts/api.md)."""
    rows = (
        db.query(GeneratedQuestion, AssessmentEvent)
        .join(
            AssessmentEvent,
            (AssessmentEvent.question_id == GeneratedQuestion.question_id)
            & (AssessmentEvent.event_type == AssessmentEventType.ANSWER_SUBMITTED),
        )
        .filter(GeneratedQuestion.quiz_session_id == quiz_session_id)
        .order_by(GeneratedQuestion.generated_at)
        .all()
    )

    total_correct = 0
    total = 0
    breakdown: dict[tuple[str, DifficultyBand], list[int]] = {}
    for question, event in rows:
        correct = bool(event.payload["correct"])
        total += 1
        total_correct += int(correct)
        counts = breakdown.setdefault((question.topic_id, question.difficulty), [0, 0])
        counts[0] += int(correct)
        counts[1] += 1

    return QuizSummary(
        score=QuizScore(correct=total_correct, total=total),
        breakdown=[
            QuizSummaryEntry(topic_id=topic_id, difficulty=difficulty, correct=c, total=t)
            for (topic_id, difficulty), (c, t) in breakdown.items()
        ],
    )


@dataclass(frozen=True)
class TimedSessionTiming:
    time_limit_seconds: int | None
    elapsed_seconds: int | None
    end_reason: str | None


def compute_timed_session_timing(
    db: Session, *, session: TimedSession, session_type: SessionKind
) -> TimedSessionTiming:
    """`time_limit_seconds`/`elapsed_seconds`/`end_reason` for a
    session's summary response (spec 022 data-model.md, contracts/
    api.md) -- all three `None` for an untimed session or a timed
    session still `in_progress` (FR-009; a partial-tally-style read,
    not an error, same precedent as `compute_quiz_summary` above).
    Reads the session's own `timed_session_ended` event -- always
    present once the session has ended, since every transition out of
    `in_progress` for a timed session writes one (`_end_timed_session`
    above, including `record_quiz_answer`'s timed-completion case).

    Deliberately a new, separate function rather than a
    `compute_quiz_summary` signature change: that function has two
    existing callers (`api/routes/quiz.py`, `api/routes/
    quiz_assignments.py`) outside this feature's Foundational-phase
    scope (spec 022 tasks.md T035/T036, not yet implemented) -- this
    keeps their current, passing behavior completely untouched (FR-009/
    SC-004) rather than breaking them mid-migration."""
    if session.time_limit_seconds is None:
        return TimedSessionTiming(time_limit_seconds=None, elapsed_seconds=None, end_reason=None)

    session_id = str(_timed_session_id(session, session_type))
    event = (
        db.query(AssessmentEvent)
        .filter(
            AssessmentEvent.learner_id == session.learner_id,
            AssessmentEvent.subject_id == session.subject_id,
            AssessmentEvent.event_type == AssessmentEventType.TIMED_SESSION_ENDED,
            AssessmentEvent.payload["session_id"].as_string() == session_id,
        )
        # PR feedback: deterministic even in the (now row-lock-prevented)
        # case of two such events existing for one session -- the most
        # recent one is the one that actually stuck.
        .order_by(AssessmentEvent.created_at.desc())
        .first()
    )
    if event is None:
        return TimedSessionTiming(
            time_limit_seconds=session.time_limit_seconds, elapsed_seconds=None, end_reason=None
        )
    return TimedSessionTiming(
        time_limit_seconds=session.time_limit_seconds,
        elapsed_seconds=event.payload["elapsed_seconds"],
        end_reason=event.payload["end_reason"],
    )
