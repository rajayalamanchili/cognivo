"""Integration test: `resolve_unlocked_grade` (spec 019 FR-009,
research.md Decision 6). Requires a reachable `DATABASE_URL` -- see
tests/conftest.py. Skips otherwise.
"""

import pytest

from src.models.grade_progress import GradeProgress
from src.services.mediation.grade import resolve_unlocked_grade

pytestmark = pytest.mark.usefixtures("database_available")


def test_returns_the_stored_unlocked_grade(db_session, demo_learner, algebra_subject):
    db_session.add(
        GradeProgress(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            unlocked_grade=7,
        )
    )
    db_session.commit()

    assert (
        resolve_unlocked_grade(
            db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
        )
        == 7
    )


def test_returns_none_when_no_grade_progress_row_exists(db_session, demo_learner, biology_subject):
    assert (
        resolve_unlocked_grade(
            db_session, learner_id=demo_learner.learner_id, subject_id=biology_subject.subject_id
        )
        is None
    )
