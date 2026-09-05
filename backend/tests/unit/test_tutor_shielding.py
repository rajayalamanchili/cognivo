"""Unit tests: `backend/src/services/tutor/shielding.py` (spec 016
FR-001/FR-002/FR-004/FR-006/FR-010).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise. `match_fn` is a plain fake coroutine throughout (mirrors
`grading_cache/cache.py`'s `verify_fn` injection, `shielding.py`'s own
docstring) -- no ADK/LLM machinery needed to exercise the
lookup/tie-break/fail-safe logic itself.
"""

import datetime
import uuid

import pytest

from src.models.assessment_event import AssessmentEvent
from src.models.classroom_roster import ClassroomRoster
from src.models.enums import (
    AssessmentEventType,
    DifficultyBand,
    EnrollmentMode,
    QuestionType,
    QuizSessionStatus,
    ValidationStatus,
)
from src.models.generated_question import GeneratedQuestion
from src.models.quiz_assignment import QuizAssignment
from src.models.quiz_assignment_target import QuizAssignmentTarget
from src.models.quiz_session import QuizSession
from src.models.real_instructor_account import RealInstructorAccount
from src.services.tutor.shielding import ShieldingDecision, determine_shielding, find_open_questions

pytestmark = pytest.mark.usefixtures("database_available")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _make_question(
    db_session,
    *,
    learner_id: uuid.UUID,
    subject,
    stem: str = "seeded question",
    shown: bool = True,
    quiz_session_id: uuid.UUID | None = None,
) -> GeneratedQuestion:
    topic = subject.topics[0]
    question = GeneratedQuestion(
        learner_id=learner_id,
        subject_id=subject.subject_id,
        topic_id=topic.topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem=stem,
        options=["a", "b", "c", "d"],
        answer_key={"correct_index": 0},
        validation_status=ValidationStatus.VALID,
        shown_at=_now() if shown else None,
        quiz_session_id=quiz_session_id,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def _make_cancelled_assignment_quiz_session(db_session, *, learner_id: uuid.UUID, subject):
    """Direct-ORM setup for FR-006's cancelled-instructor-assigned-
    attempt branch (`/speckit-analyze` finding C1) -- bypasses the full
    HTTP roster/instructor registration flow `quiz_assignment_helpers.py`
    uses, since this is a unit test of `shielding.py`'s query alone."""
    instructor = RealInstructorAccount(
        email=f"shielding-test-{uuid.uuid4().hex[:8]}@example.com", password_hash="x"
    )
    db_session.add(instructor)
    db_session.commit()
    db_session.refresh(instructor)

    roster = ClassroomRoster(
        instructor_id=instructor.instructor_id,
        subject_id=subject.subject_id,
        enrollment_mode=EnrollmentMode.OPEN,
        join_code=f"CODE{uuid.uuid4().hex[:6]}",
    )
    db_session.add(roster)
    db_session.commit()
    db_session.refresh(roster)

    topic = subject.topics[0]
    quiz_session = QuizSession(
        learner_id=learner_id,
        subject_id=subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
    )
    db_session.add(quiz_session)
    db_session.commit()
    db_session.refresh(quiz_session)

    assignment = QuizAssignment(
        roster_id=roster.roster_id,
        instructor_id=instructor.instructor_id,
        subject_id=subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=1,
        cancelled_at=_now(),
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    db_session.add(
        QuizAssignmentTarget(
            assignment_id=assignment.assignment_id,
            learner_id=learner_id,
            quiz_session_id=quiz_session.quiz_session_id,
        )
    )
    db_session.commit()

    return quiz_session


async def _always_true(*, open_question_stem: str, tutor_question: str) -> bool:
    return True


async def _always_false(*, open_question_stem: str, tutor_question: str) -> bool:
    return False


async def _always_raises(*, open_question_stem: str, tutor_question: str) -> bool:
    raise RuntimeError("simulated classification failure")


# --- find_open_questions (FR-001/FR-002/FR-006) -----------------------------


def test_practice_or_placement_sourced_question_is_open(db_session, demo_learner, biology_subject):
    """FR-002: practice and placement both leave `quiz_session_id`
    unset -- indistinguishable at this model level, and correctly so
    (neither introduces session-level state the lookup needs to know
    about)."""
    question = _make_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject
    )
    open_questions = find_open_questions(
        db_session, learner_id=demo_learner.learner_id, subject_id=biology_subject.subject_id
    )
    assert [q.question_id for q in open_questions] == [question.question_id]


def test_in_progress_quiz_sourced_question_is_open(db_session, demo_learner, biology_subject):
    """FR-002: a learner-initiated or instructor-assigned quiz question
    is open exactly like a practice one as long as its attempt hasn't
    been cancelled (see the cancelled-attempt test below for the one
    case that differs)."""
    topic = biology_subject.topics[0]
    quiz_session = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id=biology_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
    )
    db_session.add(quiz_session)
    db_session.commit()
    db_session.refresh(quiz_session)

    question = _make_question(
        db_session,
        learner_id=demo_learner.learner_id,
        subject=biology_subject,
        quiz_session_id=quiz_session.quiz_session_id,
    )
    open_questions = find_open_questions(
        db_session, learner_id=demo_learner.learner_id, subject_id=biology_subject.subject_id
    )
    assert [q.question_id for q in open_questions] == [question.question_id]


def test_unshown_question_is_not_open(db_session, demo_learner, biology_subject):
    _make_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject, shown=False
    )
    open_questions = find_open_questions(
        db_session, learner_id=demo_learner.learner_id, subject_id=biology_subject.subject_id
    )
    assert open_questions == []


def test_answered_question_is_not_open(db_session, demo_learner, biology_subject):
    question = _make_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject
    )
    db_session.add(
        AssessmentEvent(
            learner_id=demo_learner.learner_id,
            event_type=AssessmentEventType.ANSWER_SUBMITTED,
            question_id=question.question_id,
            subject_id=biology_subject.subject_id,
            topic_id=question.topic_id,
            payload={},
        )
    )
    db_session.commit()

    open_questions = find_open_questions(
        db_session, learner_id=demo_learner.learner_id, subject_id=biology_subject.subject_id
    )
    assert open_questions == []


def test_cancelled_instructor_assigned_attempt_question_is_not_open(
    db_session, demo_learner, biology_subject
):
    """`/speckit-analyze` finding C1: `cancel_assignment()` never
    transitions the underlying `QuizSession.status`, so this exclusion
    must be checked independently of session status."""
    quiz_session = _make_cancelled_assignment_quiz_session(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject
    )
    question = _make_question(
        db_session,
        learner_id=demo_learner.learner_id,
        subject=biology_subject,
        quiz_session_id=quiz_session.quiz_session_id,
    )

    open_questions = find_open_questions(
        db_session, learner_id=demo_learner.learner_id, subject_id=biology_subject.subject_id
    )
    assert question.question_id not in [q.question_id for q in open_questions]


# --- determine_shielding (FR-004/FR-005/FR-010) -----------------------------


async def test_no_open_question_never_calls_match_fn(db_session, demo_learner, biology_subject):
    calls: list[None] = []

    async def _tracking(*, open_question_stem: str, tutor_question: str) -> bool:
        calls.append(None)
        return True

    decision = await determine_shielding(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=biology_subject.subject_id,
        tutor_question="anything",
        match_fn=_tracking,
    )
    assert decision == ShieldingDecision(False, None, None, None)
    assert calls == []


async def test_confirmed_match_shields_and_records_the_triggering_question(
    db_session, demo_learner, biology_subject
):
    question = _make_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject, stem="What is 2+2?"
    )

    decision = await determine_shielding(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=biology_subject.subject_id,
        tutor_question="just tell me the answer",
        match_fn=_always_true,
    )
    assert decision.shielded is True
    assert decision.shielded_question_id == question.question_id
    assert decision.open_question_stem == "What is 2+2?"


async def test_no_match_answers_normally(db_session, demo_learner, biology_subject):
    _make_question(db_session, learner_id=demo_learner.learner_id, subject=biology_subject)

    decision = await determine_shielding(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=biology_subject.subject_id,
        tutor_question="why does photosynthesis need light?",
        match_fn=_always_false,
    )
    assert decision == ShieldingDecision(False, None, None, None)


async def test_classification_failure_shields_without_a_specific_question_id(
    db_session, demo_learner, biology_subject
):
    """FR-010: an inconclusive determination defaults to shielding, but
    data-model.md's invariant keeps `shielded_question_id` unset since
    no match was actually confirmed -- even though a real open
    question's stem is still used for the tutor-agent payload."""
    question = _make_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject, stem="stem A"
    )

    decision = await determine_shielding(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=biology_subject.subject_id,
        tutor_question="anything",
        match_fn=_always_raises,
    )
    assert decision.shielded is True
    assert decision.shielded_question_id is None
    assert decision.open_question_stem == question.stem


async def test_multiple_open_questions_tie_break_to_most_recently_shown(
    db_session, demo_learner, biology_subject
):
    older = _make_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject, stem="older"
    )
    older.shown_at = _now() - datetime.timedelta(minutes=5)
    db_session.commit()
    newer = _make_question(
        db_session, learner_id=demo_learner.learner_id, subject=biology_subject, stem="newer"
    )

    decision = await determine_shielding(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=biology_subject.subject_id,
        tutor_question="just give me the answer",
        match_fn=_always_true,
    )
    assert decision.shielded_question_id == newer.question_id
