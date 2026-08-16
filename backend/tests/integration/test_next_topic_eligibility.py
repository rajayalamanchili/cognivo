"""Integration test: next-topic eligibility, deterministic tie-breaking,
and difficulty derivation (FR-006), T043.

Exercises `select_next_topic` directly against a real Postgres-backed
content artifact and hand-crafted `MasteryState` rows -- topic selection
itself must be fully deterministic given DB state (Constitution
Principle I), independent of question generation/LLM calls, so no
mocking is needed here.
"""

from src.agents.sequencing.agent import select_next_topic
from src.models.mastery_state import MasteryState

MASTERED_P = 0.9
MASTERED_CONSECUTIVE = 2


def _set_mastery(db_session, learner_id, subject_id, topic_id, *, p_mastery, consecutive=0):
    state = MasteryState(
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        p_mastery=p_mastery,
        update_count=1,
        consecutive_mastered_observations=consecutive,
    )
    db_session.add(state)
    db_session.commit()
    return state


def test_topic_with_unsatisfied_prerequisite_is_not_eligible(
    db_session, demo_learner, algebra_subject
):
    # No MasteryState rows at all -- only the two zero-prerequisite entry
    # topics can be eligible; every other topic is prerequisite-blocked.
    selection = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    assert selection.topic_id in ("integers-and-operations", "variables-and-expressions")
    assert selection.band == "unknown"
    assert selection.difficulty.value == "easy"
    assert selection.is_fallback is False


def test_unknown_ranked_ahead_of_any_numeric_p_mastery(db_session, demo_learner, algebra_subject):
    # variables-and-expressions has a low-but-real p_mastery; integers-
    # and-operations is still "unknown" -- unknown must win regardless of
    # its numeric value (data-model.md: unknown sorts ahead of any
    # numeric p_mastery).
    _set_mastery(
        db_session,
        demo_learner.learner_id,
        algebra_subject.subject_id,
        "variables-and-expressions",
        p_mastery=0.01,
    )
    selection = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    assert selection.topic_id == "integers-and-operations"
    assert selection.band == "unknown"


def test_tie_broken_by_ascending_order_index(db_session, demo_learner, algebra_subject):
    # Mastering both entry topics unblocks order-of-operations (prereq:
    # integers-and-operations) and solving-one-step-equations (prereq:
    # variables-and-expressions). Both newly-eligible topics are
    # "unknown" (tied) -- order_index must break the tie.
    _set_mastery(
        db_session,
        demo_learner.learner_id,
        algebra_subject.subject_id,
        "integers-and-operations",
        p_mastery=MASTERED_P,
        consecutive=MASTERED_CONSECUTIVE,
    )
    _set_mastery(
        db_session,
        demo_learner.learner_id,
        algebra_subject.subject_id,
        "variables-and-expressions",
        p_mastery=MASTERED_P,
        consecutive=MASTERED_CONSECUTIVE,
    )
    selection = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    # order-of-operations (order_index 2) precedes
    # solving-one-step-equations (order_index 3).
    assert selection.topic_id == "order-of-operations"
    assert selection.band == "unknown"


def test_developing_topic_selected_yields_medium_difficulty(
    db_session, demo_learner, algebra_subject
):
    # Master integers-and-operations, variables-and-expressions, and
    # order-of-operations so solving-one-step-equations is the ONLY
    # eligible topic (isolating it, since an "unknown" eligible topic
    # would otherwise always outrank a "developing" one).
    for topic_id in ("integers-and-operations", "variables-and-expressions", "order-of-operations"):
        _set_mastery(
            db_session,
            demo_learner.learner_id,
            algebra_subject.subject_id,
            topic_id,
            p_mastery=MASTERED_P,
            consecutive=MASTERED_CONSECUTIVE,
        )
    _set_mastery(
        db_session,
        demo_learner.learner_id,
        algebra_subject.subject_id,
        "solving-one-step-equations",
        p_mastery=0.5,
    )
    selection = select_next_topic(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    assert selection.topic_id == "solving-one-step-equations"
    assert selection.band == "developing"
    assert selection.difficulty.value == "medium"
    assert selection.is_fallback is False
