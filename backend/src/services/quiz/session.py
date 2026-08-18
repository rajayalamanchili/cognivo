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

from google.adk.sessions import BaseSessionService
from sqlalchemy.orm import Session

from src.agents.assessment_gen.agent import GeneratedQuestionDraft, generate_question
from src.agents.diagnostic.agent import difficulty_guidance, preferred_question_type, skill_summary
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType, DifficultyBand, QuestionType, QuizSessionStatus
from src.models.generated_question import GeneratedQuestion
from src.models.quiz_session import QuizSession
from src.models.topic import Topic
from src.services.audit_log.writer import record_event
from src.services.dedup.checker import is_near_duplicate, recent_stems_for_topic
from src.services.quiz.difficulty import (
    current_difficulty_for_topic,
    next_difficulty,
    replay_topic_state,
)

DEFAULT_MAX_DEDUP_ATTEMPTS = 3


class QuizEndedEarlyError(Exception):
    """Raised when a fresh, distinct question cannot be generated for a
    topic after exhausting dedup retries (FR-008) -- the caller must
    transition `QuizSession.status` to `ended_early` rather than serve
    a near-duplicate (research.md §3)."""


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
) -> QuizSession:
    """Persists a new `QuizSession` row (`status=in_progress`). Does not
    commit, and does not validate `topic_ids`/`question_count` -- the
    caller (the API route) is responsible for FR-001's request-shape
    validation before calling this, matching this codebase's existing
    convention of validating in the route layer."""
    quiz = QuizSession(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_ids=list(topic_ids),
        question_count=question_count,
    )
    db.add(quiz)
    db.flush()
    return quiz


def _topic_answer_history(db: Session, *, quiz_session_id: uuid.UUID, topic_id: str) -> list[bool]:
    """This quiz's ordered (correct/incorrect) history for `topic_id`,
    generation order -- only questions already answered, since an
    unanswered question hasn't produced a difficulty decision yet."""
    rows = (
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
        .order_by(GeneratedQuestion.generated_at)
        .all()
    )
    return [event.payload["correct"] for _question, event in rows]


@dataclass(frozen=True)
class QuizQuestionResult:
    topic_id: str
    question_type: QuestionType
    difficulty: DifficultyBand
    draft: GeneratedQuestionDraft


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

    for _ in range(max_dedup_attempts):
        draft = await generate_question(
            topic_display_name=topic.display_name,
            skill_summary=skill_summary(topic),
            difficulty=difficulty,
            difficulty_guidance=difficulty_guidance(topic, difficulty),
            question_type=question_type,
            session_service=session_service,
            avoid_stems=recent_stems,
        )
        if not is_near_duplicate(draft.stem, recent_stems):
            return QuizQuestionResult(
                topic_id=topic_id, question_type=question_type, difficulty=difficulty, draft=draft
            )

    raise QuizEndedEarlyError(
        f"quiz {quiz.quiz_session_id}: could not generate a fresh question for topic "
        f"{topic_id!r} after {max_dedup_attempts} attempts"
    )


def record_quiz_answer(db: Session, *, question: GeneratedQuestion, correct: bool) -> None:
    """Called from the quiz-aware branch of `answer_question` (research.md
    §4), regardless of ordering relative to the shared `ANSWER_SUBMITTED`
    event: logs the `quiz_difficulty_adjusted` decision (FR-009) using
    this topic's *prior* history only (deliberately excludes this
    just-submitted answer's own event, whether or not it has been
    written yet), and flips `QuizSession.status` to `completed` once
    this quiz's answered-question count reaches `question_count`."""
    quiz = db.get(QuizSession, question.quiz_session_id)

    prior_history = _topic_answer_history(
        db, quiz_session_id=quiz.quiz_session_id, topic_id=question.topic_id
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
        )
        .count()
    )
    if answered_count_before + 1 >= quiz.question_count:
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
