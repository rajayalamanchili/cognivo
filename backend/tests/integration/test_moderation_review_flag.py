"""Integration test: `is_flagged_for_review()` returns `true` once a
learner crosses the locked moderation-flag threshold within the rolling
window, `false` otherwise (spec 007 FR-013), T022.
"""

from src.models.enums import AssessmentEventType
from src.services.audit_log.writer import record_event
from src.services.grading_client.moderation_review import (
    ESCALATION_THRESHOLD,
    is_flagged_for_review,
)


def _write_moderation_rejection(db_session, learner, subject, topic_id, *, reason="moderation"):
    record_event(
        db_session,
        learner_id=learner.learner_id,
        event_type=AssessmentEventType.FREE_TEXT_SUBMISSION_REJECTED,
        subject_id=subject.subject_id,
        topic_id=topic_id,
        payload={"reason": reason, "submitted_text": "x", "length": 1},
    )
    db_session.commit()


def test_not_flagged_below_threshold(db_session, demo_learner, algebra_subject):
    topic_id = algebra_subject.topics[0].topic_id
    for _ in range(ESCALATION_THRESHOLD - 1):
        _write_moderation_rejection(db_session, demo_learner, algebra_subject, topic_id)

    assert is_flagged_for_review(db_session, learner_id=demo_learner.learner_id) is False


def test_flagged_at_threshold(db_session, demo_learner, algebra_subject):
    topic_id = algebra_subject.topics[0].topic_id
    for _ in range(ESCALATION_THRESHOLD):
        _write_moderation_rejection(db_session, demo_learner, algebra_subject, topic_id)

    assert is_flagged_for_review(db_session, learner_id=demo_learner.learner_id) is True


def test_non_moderation_rejections_never_count_toward_escalation(
    db_session, demo_learner, algebra_subject
):
    topic_id = algebra_subject.topics[0].topic_id
    for _ in range(ESCALATION_THRESHOLD + 5):
        _write_moderation_rejection(
            db_session, demo_learner, algebra_subject, topic_id, reason="too_long"
        )

    assert is_flagged_for_review(db_session, learner_id=demo_learner.learner_id) is False
