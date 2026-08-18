"""Integration test: next-step suggestions against the real `algebra-1`
content artifact -- every suggestion references a real topic, and
prerequisite-gap suggestions surface the prerequisite rather than the
original weak topic (SC-003, FR-006, FR-007), T014.

`solving-multi-step-equations` has two real prerequisites
(`solving-one-step-equations`, `order-of-operations`, per
`content/algebra-1/subject.yaml`) -- exercising the multi-prerequisite
tie-break (research.md §5) against real content, not a synthetic graph.
"""

from src.models.topic import Topic
from src.services.recommendation.next_step import NextStepReason, suggest_next_step
from tests.integration.recommendation.scenarios import make_mastered_topic, make_weak_topic


def test_single_level_prerequisite_gap_against_real_content(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.2,
    )
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
        p_mastery=0.1,
    )

    result = suggest_next_step(
        db_session, learner_id=learner_id, subject_id=subject_id, topic_id="order-of-operations"
    )

    assert result.reason is NextStepReason.PREREQUISITE_GAP
    assert result.recommended_topic_id == "integers-and-operations"
    assert result.prerequisite_chain == ["integers-and-operations"]


def test_multi_prerequisite_tie_break_against_real_content(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-multi-step-equations",
        p_mastery=0.2,
    )
    # Both real prerequisites struggling, different p_mastery --
    # order-of-operations (lower) must win over solving-one-step-equations.
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-one-step-equations",
        p_mastery=0.3,
    )
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.15,
    )
    # order-of-operations' own prerequisite is mastered, so recursion
    # stops there.
    make_mastered_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
    )

    result = suggest_next_step(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-multi-step-equations",
    )

    assert result.reason is NextStepReason.PREREQUISITE_GAP
    assert result.recommended_topic_id == "order-of-operations"
    assert result.prerequisite_chain == ["order-of-operations"]


def test_direct_practice_when_all_real_prerequisites_mastered(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.2,
    )
    make_mastered_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
    )

    result = suggest_next_step(
        db_session, learner_id=learner_id, subject_id=subject_id, topic_id="order-of-operations"
    )

    assert result.reason is NextStepReason.DIRECT_PRACTICE
    assert result.recommended_topic_id == "order-of-operations"
    assert result.prerequisite_chain == []


def test_prerequisite_not_yet_assessed_stops_recursion(db_session, demo_learner, algebra_subject):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.2,
    )
    # integers-and-operations left untouched -- no MasteryState row.

    result = suggest_next_step(
        db_session, learner_id=learner_id, subject_id=subject_id, topic_id="order-of-operations"
    )

    assert result.reason is NextStepReason.PREREQUISITE_NOT_YET_ASSESSED
    assert result.recommended_topic_id == "integers-and-operations"


def test_every_suggestion_references_a_real_topic(db_session, demo_learner, algebra_subject):
    # SC-003: recommended_topic_id and every prerequisite_chain entry
    # must reference a real topic in the subject's content artifact --
    # never a fabricated name.
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-multi-step-equations",
        p_mastery=0.2,
    )
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-one-step-equations",
        p_mastery=0.3,
    )
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.15,
    )
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
        p_mastery=0.05,
    )

    real_topic_ids = {
        topic.topic_id
        for topic in db_session.query(Topic).filter(Topic.subject_id == subject_id).all()
    }

    result = suggest_next_step(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="solving-multi-step-equations",
    )

    assert result.recommended_topic_id in real_topic_ids
    assert all(topic_id in real_topic_ids for topic_id in result.prerequisite_chain)
    # Recurses through order-of-operations to the deepest root cause.
    assert result.prerequisite_chain == ["order-of-operations", "integers-and-operations"]
    assert result.recommended_topic_id == "integers-and-operations"
