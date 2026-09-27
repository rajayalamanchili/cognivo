"""Integration test: mastery decay re-ranks the mastered-topic fallback
by real DB state (spec 024 US1, FR-003/FR-005/SC-001/SC-004).

Extends `test_next_topic_fallback.py`'s existing "every topic mastered"
fixture pattern with one row's `updated_at` backdated past
`GRACE_PERIOD + HALF_LIFE` -- the more time-decayed topic must win the
fallback pick even when its raw `p_mastery` is equal to (not lower
than) the other topic's.
"""

import datetime

from src.agents.sequencing.agent import select_next_topic
from src.models.grade_progress import GradeProgress
from src.models.mastery_state import MasteryState
from src.services.mastery.decay import GRACE_PERIOD, HALF_LIFE

_ALGEBRA_TOPIC_IDS_IN_ORDER = [
    "integers-and-operations",
    "variables-and-expressions",
    "order-of-operations",
    "solving-one-step-equations",
    "solving-multi-step-equations",
    "linear-inequalities",
    "graphing-linear-equations",
    "systems-of-linear-equations",
]

_DECAYED_TOPIC = "linear-inequalities"
_FRESH_TOPIC = "graphing-linear-equations"


def _master_all_topics_with_one_decayed(db_session, learner_id, subject_id):
    db_session.add(GradeProgress(learner_id=learner_id, subject_id=subject_id, unlocked_grade=8))
    db_session.commit()

    now = datetime.datetime.now(datetime.UTC)
    backdated = now - GRACE_PERIOD - HALF_LIFE * 3

    for topic_id in _ALGEBRA_TOPIC_IDS_IN_ORDER:
        updated_at = backdated if topic_id == _DECAYED_TOPIC else now
        db_session.add(
            MasteryState(
                learner_id=learner_id,
                subject_id=subject_id,
                topic_id=topic_id,
                p_mastery=0.8,
                update_count=1,
                consecutive_mastered_observations=2,
                updated_at=updated_at,
            )
        )
    db_session.commit()
    return now


def test_more_decayed_mastered_topic_wins_fallback_despite_equal_raw_p_mastery(
    db_session, demo_learner, algebra_subject
):
    _master_all_topics_with_one_decayed(
        db_session, demo_learner.learner_id, algebra_subject.subject_id
    )

    selection = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )

    assert selection.is_fallback is True
    assert selection.topic_id == _DECAYED_TOPIC
    # FR-005: the returned mastery is the raw, undecayed value -- never
    # the decayed one used only for sorting.
    assert selection.p_mastery == 0.8


def test_selection_is_reproducible_given_identical_state(db_session, demo_learner, algebra_subject):
    _master_all_topics_with_one_decayed(
        db_session, demo_learner.learner_id, algebra_subject.subject_id
    )

    first = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    second = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )

    assert first.topic_id == second.topic_id == _DECAYED_TOPIC
