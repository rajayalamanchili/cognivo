"""Integration test: Sequencing and Recommendation may name different
topics on the same mastery state without that being a bug (FR-010,
User Story 4), T024.

Feeds one scripted mastery-state fixture to both Sequencing's real
`select_next_topic` (imported from `src`, never from a Sequencing test
file -- FR-009/SC-005) and Recommendation's `classify_topics`, and
confirms each independently names a different topic as most urgent,
each traceable via its own reasoning.
"""

from src.agents.sequencing.agent import select_next_topic
from src.services.recommendation.weak_area import classify_topics
from tests.integration.recommendation.scenarios import make_weak_topic


def test_sequencing_and_recommendation_may_name_different_topics(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    # variables-and-expressions is confidently weak; integers-and-
    # operations is left untouched -- "unknown" to Sequencing.
    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="variables-and-expressions",
        p_mastery=0.1,
    )

    sequencing_selection = select_next_topic(
        db_session, learner_id=learner_id, subject_id=subject_id
    )
    recommendation_report = classify_topics(
        db_session, learner_id=learner_id, subject_id=subject_id
    )

    # Sequencing prioritizes assessing the unknown entry-level topic --
    # "unknown" ranks ahead of any numeric p_mastery (001's data-model.md).
    assert sequencing_selection.topic_id == "integers-and-operations"
    assert sequencing_selection.band == "unknown"

    # Recommendation flags the confidently-weak topic instead -- a
    # genuinely different, and equally correct, answer to a different
    # question (FR-010): what to assess right now vs. a broader pattern
    # across the learner's whole history.
    weak_topic_ids = {flag.topic_id for flag in recommendation_report.weak_areas}
    assert weak_topic_ids == {"variables-and-expressions"}
    assert sequencing_selection.topic_id not in weak_topic_ids

    # Each is independently traceable via its own reasoning, without
    # needing to reconcile with the other.
    assert sequencing_selection.candidates_considered
    assert recommendation_report.weak_areas[0].evidence
