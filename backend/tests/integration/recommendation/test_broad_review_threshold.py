"""Integration test: `broad_review_needed` switches on at FR-005's 60%
proportion of confidently-assessed topics in the struggling band, T011.
"""

from src.services.recommendation.weak_area import classify_topics
from tests.integration.recommendation.scenarios import make_mastered_topic, make_weak_topic


def test_broad_review_needed_true_at_exactly_sixty_percent(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    # 3 of 5 confidently-assessed topics struggling = exactly 60%.
    for topic_id in ("integers-and-operations", "variables-and-expressions", "order-of-operations"):
        make_weak_topic(db_session, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id)
    for topic_id in ("solving-one-step-equations", "solving-multi-step-equations"):
        make_mastered_topic(
            db_session, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id
        )

    report = classify_topics(db_session, learner_id=learner_id, subject_id=subject_id)

    assert report.broad_review_needed is True
    # The full flagged list is still populated -- the API never
    # truncates to a "top N" (FR-005, contracts/api.md).
    assert len(report.weak_areas) == 3


def test_broad_review_needed_false_just_under_sixty_percent(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    # 2 of 5 confidently-assessed topics struggling = 40%, under the
    # threshold.
    for topic_id in ("integers-and-operations", "variables-and-expressions"):
        make_weak_topic(db_session, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id)
    for topic_id in (
        "order-of-operations",
        "solving-one-step-equations",
        "solving-multi-step-equations",
    ):
        make_mastered_topic(
            db_session, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id
        )

    report = classify_topics(db_session, learner_id=learner_id, subject_id=subject_id)

    assert report.broad_review_needed is False
    assert len(report.weak_areas) == 2


def test_broad_review_needed_false_when_nothing_confidently_assessed(
    db_session, demo_learner, algebra_subject
):
    # Zero confidently-assessed topics -- FR-004's insufficient-data
    # gate already applies; broad_review_needed must not spuriously
    # compute true off a zero-denominator division.
    report = classify_topics(
        db_session, learner_id=demo_learner.learner_id, subject_id=algebra_subject.subject_id
    )
    assert report.data_sufficiency == "insufficient_data"
    assert report.broad_review_needed is False
