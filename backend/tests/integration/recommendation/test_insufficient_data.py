"""Integration test: insufficient-data verdict when every assessed
topic has fewer than 3 recorded events (SC-004, FR-004), including the
single-wrong-answer edge case (spec.md Edge Cases), T010.
"""

from src.services.recommendation.weak_area import classify_topics
from tests.integration.recommendation.scenarios import (
    make_insufficient_data_topic,
    make_weak_topic,
)


def test_brand_new_learner_is_insufficient_data(db_session, demo_learner, algebra_subject):
    # Zero MasteryState rows at all -- vacuously "every assessed topic
    # falls below the per-topic minimum" (FR-004).
    report = classify_topics(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    assert report.data_sufficiency == "insufficient_data"
    assert report.weak_areas == []
    assert report.broad_review_needed is False


def test_every_touched_topic_below_minimum_is_insufficient_data(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_insufficient_data_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
        num_events=2,
    )
    make_insufficient_data_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="variables-and-expressions",
        num_events=1,
    )

    report = classify_topics(db_session, learner_id=learner_id, subject_id=subject_id)

    assert report.data_sufficiency == "insufficient_data"
    assert report.weak_areas == []
    assert set(report.insufficient_data_topic_ids) == {
        "integers-and-operations",
        "variables-and-expressions",
    }


def test_single_wrong_answer_does_not_produce_a_confident_weak_flag(
    db_session, demo_learner, algebra_subject
):
    # A single wrong answer alone (spec.md Edge Cases) must not
    # overreact into a confidently-worded weak-area flag, even though
    # the raw posterior already dipped into the struggling band.
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_insufficient_data_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
        num_events=1,
        p_mastery=0.05,
    )

    report = classify_topics(db_session, learner_id=learner_id, subject_id=subject_id)

    assert report.data_sufficiency == "insufficient_data"
    assert report.weak_areas == []
    assert report.insufficient_data_topic_ids == ["integers-and-operations"]


def test_mixed_confident_and_insufficient_topics_is_still_confident_overall(
    db_session, demo_learner, algebra_subject
):
    # If at least one topic reaches the per-topic minimum, the overall
    # report is confident -- FR-004's "insufficient data" gate is about
    # *every* assessed topic, not any single one.
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="integers-and-operations",
        num_events=3,
    )
    make_insufficient_data_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="variables-and-expressions",
        num_events=1,
    )

    report = classify_topics(db_session, learner_id=learner_id, subject_id=subject_id)

    assert report.data_sufficiency == "confident"
    assert [flag.topic_id for flag in report.weak_areas] == ["integers-and-operations"]
    assert report.insufficient_data_topic_ids == ["variables-and-expressions"]
