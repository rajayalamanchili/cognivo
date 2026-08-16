"""Integration test: zero-eligible-topics fallback (FR-006), T044.

When every topic is "mastered" or prerequisite-blocked, `select_next_topic`
must fall back to the lowest-`p_mastery` "mastered" topic (review)
instead of erroring -- ties broken by `Topic.order_index`, the same rule
used for the eligible-topic case (data-model.md).
"""

from src.agents.sequencing.agent import select_next_topic
from src.models.mastery_state import MasteryState

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


def _master_all_topics(db_session, learner_id, subject_id, *, p_mastery_by_topic=None):
    p_mastery_by_topic = p_mastery_by_topic or {}
    for topic_id in _ALGEBRA_TOPIC_IDS_IN_ORDER:
        db_session.add(
            MasteryState(
                learner_id=learner_id,
                subject_id=subject_id,
                topic_id=topic_id,
                p_mastery=p_mastery_by_topic.get(topic_id, 0.9),
                update_count=1,
                consecutive_mastered_observations=2,
            )
        )
    db_session.commit()


def test_fallback_selects_lowest_p_mastery_mastered_topic(
    db_session, demo_learner, algebra_subject
):
    _master_all_topics(
        db_session,
        demo_learner.learner_id,
        algebra_subject.subject_id,
        p_mastery_by_topic={"linear-inequalities": 0.71},
    )
    selection = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    assert selection.is_fallback is True
    assert selection.topic_id == "linear-inequalities"
    assert selection.band == "mastered"
    assert selection.difficulty.value == "hard"


def test_fallback_tie_broken_by_order_index(db_session, demo_learner, algebra_subject):
    _master_all_topics(
        db_session,
        demo_learner.learner_id,
        algebra_subject.subject_id,
        p_mastery_by_topic={
            "solving-multi-step-equations": 0.71,
            "graphing-linear-equations": 0.71,
        },
    )
    selection = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    assert selection.is_fallback is True
    # solving-multi-step-equations (order_index 4) precedes
    # graphing-linear-equations (order_index 6).
    assert selection.topic_id == "solving-multi-step-equations"
