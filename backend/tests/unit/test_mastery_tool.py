"""Unit tests: `apply_mastery_update`'s grade-unlock check (spec 017
User Story 2 FR-004, T024).

Requires a reachable `DATABASE_URL` (mirrors `test_question_cache.py`) --
`apply_mastery_update` reads/writes real `MasteryState`/`GradeProgress`
rows, so this isn't a pure-function test like `test_sequencing.py`.
Uses the real `algebra-1` content artifact (grade_bands [6, 7, 8]) and
`biology` (ungraded) as fixtures already establish.
"""

import pytest

from src.agents.sequencing.mastery_tool import apply_mastery_update
from src.models.enums import QuestionType
from src.models.grade_progress import GradeProgress

pytestmark = pytest.mark.usefixtures("database_available")

GRADE_6_TOPICS = ["integers-and-operations", "variables-and-expressions", "solving-one-step-equations"]
GRADE_8_TOPICS = ["systems-of-linear-equations"]


def _master(db_session, *, learner_id, subject_id, topic_id, attempts=3):
    """3 consecutive correct multiple_choice answers crosses 0.7 and
    confirms the 2-consecutive-observation streak (MASTERY_CONFIRMATION_THRESHOLD)
    -- reaches "mastered" regardless of the topic's own declared
    preferred_question_types, since apply_mastery_update doesn't care."""
    result = None
    for _ in range(attempts):
        result = apply_mastery_update(
            db_session,
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            correct=True,
            question_type=QuestionType.MULTIPLE_CHOICE,
        )
    db_session.commit()
    return result


def test_completing_every_topic_in_current_grade_unlocks_next_declared_grade(
    db_session, demo_learner, algebra_subject
):
    db_session.add(
        GradeProgress(learner_id=demo_learner.learner_id, subject_id="algebra-1", unlocked_grade=6)
    )
    db_session.commit()

    for topic_id in GRADE_6_TOPICS[:-1]:
        result = _master(
            db_session, learner_id=demo_learner.learner_id, subject_id="algebra-1", topic_id=topic_id
        )
        assert result.grade_unlocked is None

    final_result = _master(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=GRADE_6_TOPICS[-1],
    )
    assert final_result.grade_unlocked == 7

    progress = db_session.get(GradeProgress, (demo_learner.learner_id, "algebra-1"))
    assert progress.unlocked_grade == 7


def test_incomplete_grade_returns_none(db_session, demo_learner, algebra_subject):
    db_session.add(
        GradeProgress(learner_id=demo_learner.learner_id, subject_id="algebra-1", unlocked_grade=6)
    )
    db_session.commit()

    for topic_id in GRADE_6_TOPICS[:-1]:
        result = _master(
            db_session, learner_id=demo_learner.learner_id, subject_id="algebra-1", topic_id=topic_id
        )
        assert result.grade_unlocked is None

    progress = db_session.get(GradeProgress, (demo_learner.learner_id, "algebra-1"))
    assert progress.unlocked_grade == 6


def test_completing_highest_declared_grade_returns_none_no_error(
    db_session, demo_learner, algebra_subject
):
    db_session.add(
        GradeProgress(learner_id=demo_learner.learner_id, subject_id="algebra-1", unlocked_grade=8)
    )
    db_session.commit()

    result = _master(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id="algebra-1",
        topic_id=GRADE_8_TOPICS[0],
    )
    assert result.grade_unlocked is None

    progress = db_session.get(GradeProgress, (demo_learner.learner_id, "algebra-1"))
    assert progress.unlocked_grade == 8


def test_ungraded_topic_never_triggers_check(db_session, demo_learner, biology_subject):
    # No GradeProgress row is ever created for an ungraded subject
    # (FR-009) -- mastering a biology topic must never attempt the
    # unlock check at all.
    first_topic_id = biology_subject.topics[0].topic_id
    result = _master(
        db_session, learner_id=demo_learner.learner_id, subject_id="biology", topic_id=first_topic_id
    )
    assert result.grade_unlocked is None
    assert db_session.get(GradeProgress, (demo_learner.learner_id, "biology")) is None


def test_already_unlocked_grade_not_reverted_by_mastery_regression(
    db_session, demo_learner, algebra_subject
):
    db_session.add(
        GradeProgress(learner_id=demo_learner.learner_id, subject_id="algebra-1", unlocked_grade=6)
    )
    db_session.commit()

    for topic_id in GRADE_6_TOPICS:
        _master(db_session, learner_id=demo_learner.learner_id, subject_id="algebra-1", topic_id=topic_id)

    progress = db_session.get(GradeProgress, (demo_learner.learner_id, "algebra-1"))
    assert progress.unlocked_grade == 7

    # Drive a grade-6 topic's mastery back down below the mastered band.
    for _ in range(5):
        result = apply_mastery_update(
            db_session,
            learner_id=demo_learner.learner_id,
            subject_id="algebra-1",
            topic_id=GRADE_6_TOPICS[0],
            correct=False,
            question_type=QuestionType.MULTIPLE_CHOICE,
        )
        assert result.grade_unlocked is None
    db_session.commit()

    progress = db_session.get(GradeProgress, (demo_learner.learner_id, "algebra-1"))
    assert progress.unlocked_grade == 7
