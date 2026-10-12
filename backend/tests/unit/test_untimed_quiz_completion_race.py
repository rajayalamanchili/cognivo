"""Unit test: for an *untimed* quiz, `record_quiz_answer`'s and
`end_quiz_for_dedup_exhaustion`'s completion branches previously set
`status` unconditionally, with no row lock or re-check -- unlike the
timed branch (`test_timed_quiz_completion_race.py`'s PR #83 finding).
A concurrent duplicate/retried request reaching either branch could
clobber a status the other had just set (review finding, PR #113).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime

from src.models.enums import (
    AssessmentEventType,
    DifficultyBand,
    QuestionType,
    QuizSessionStatus,
    ValidationStatus,
)
from src.models.generated_question import GeneratedQuestion
from src.models.quiz_session import QuizSession
from src.services.audit_log.writer import record_event
from src.services.quiz.session import end_quiz_for_dedup_exhaustion, record_quiz_answer


def _untimed_quiz_and_question(db_session, *, demo_learner, algebra_subject):
    topic = algebra_subject.topics[0]
    quiz = QuizSession(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_ids=[topic.topic_id],
        question_count=1,
        status=QuizSessionStatus.IN_PROGRESS,
        time_limit_seconds=None,
    )
    db_session.add(quiz)
    db_session.flush()

    question = GeneratedQuestion(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.NUMERIC,
        stem="2 + 2",
        answer_key={"correct_value": 4},
        validation_status=ValidationStatus.VALID,
        shown_at=datetime.datetime.now(datetime.UTC),
        quiz_session_id=quiz.quiz_session_id,
    )
    db_session.add(question)
    db_session.flush()

    record_event(
        db_session,
        learner_id=demo_learner.learner_id,
        event_type=AssessmentEventType.ANSWER_SUBMITTED,
        subject_id=algebra_subject.subject_id,
        topic_id=topic.topic_id,
        question_id=question.question_id,
        payload={"response": 4, "correct": True},
    )
    db_session.flush()
    return quiz, question


def test_answer_completion_does_not_clobber_concurrent_dedup_exhaustion(
    db_session, demo_learner, algebra_subject
):
    """Request B (dedup exhaustion on a duplicate next-question call)
    races ahead and commits `ended_early` first; request A reaching
    the answer-completion branch afterward must not overwrite it with
    `completed`."""
    quiz, question = _untimed_quiz_and_question(
        db_session, demo_learner=demo_learner, algebra_subject=algebra_subject
    )

    end_quiz_for_dedup_exhaustion(db_session, quiz=quiz)
    db_session.commit()
    assert quiz.status == QuizSessionStatus.ENDED_EARLY
    ended_at = quiz.completed_at

    record_quiz_answer(db_session, question=question, correct=True)
    db_session.commit()

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.ENDED_EARLY
    assert quiz.completed_at == ended_at


def test_dedup_exhaustion_does_not_clobber_concurrent_answer_completion(
    db_session, demo_learner, algebra_subject
):
    """Mirror of the above with the two requests in the opposite order:
    the answer-completion branch commits `completed` first; dedup
    exhaustion reaching its own branch afterward must not overwrite it
    with `ended_early`."""
    quiz, question = _untimed_quiz_and_question(
        db_session, demo_learner=demo_learner, algebra_subject=algebra_subject
    )

    record_quiz_answer(db_session, question=question, correct=True)
    db_session.commit()
    assert quiz.status == QuizSessionStatus.COMPLETED
    completed_at = quiz.completed_at

    end_quiz_for_dedup_exhaustion(db_session, quiz=quiz)
    db_session.commit()

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.COMPLETED
    assert quiz.completed_at == completed_at


def test_answer_completion_still_completes_when_nothing_raced_it(
    db_session, demo_learner, algebra_subject
):
    """Control case: with no concurrent transition, the lock+re-check
    must not block the ordinary untimed completion path."""
    quiz, question = _untimed_quiz_and_question(
        db_session, demo_learner=demo_learner, algebra_subject=algebra_subject
    )

    record_quiz_answer(db_session, question=question, correct=True)
    db_session.commit()

    db_session.refresh(quiz)
    assert quiz.status == QuizSessionStatus.COMPLETED
    assert quiz.completed_at is not None
