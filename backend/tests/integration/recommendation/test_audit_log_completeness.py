"""Integration test: full audit-log completeness for a
`/recommendations` request (FR-008, User Story 3), T020.

Confirms one `recommendation_report_generated` row, one
`weak_area_flagged` row per flagged topic, and one `next_step_suggested`
row per suggestion -- each with enough payload detail to reconstruct
the decision (Constitution Principle V's "why was this topic flagged").
No LLM call is involved (research.md §1), so unlike Milestone 1's own
audit-log test, nothing needs mocking here.
"""

from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from tests.integration.recommendation.scenarios import make_weak_topic


def test_audit_log_completeness_for_a_recommendations_request(
    db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
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

    response = client.get(
        f"/api/learners/{learner_id}/recommendations", params={"subject_id": subject_id}
    )
    assert response.status_code == 200, response.text
    weak_area_count = len(response.json()["weak_areas"])
    assert weak_area_count == 2

    events = (
        db_session.query(AssessmentEvent).filter(AssessmentEvent.learner_id == learner_id).all()
    )
    by_type: dict[AssessmentEventType, list[AssessmentEvent]] = {}
    for event in events:
        by_type.setdefault(event.event_type, []).append(event)

    # One row per report request.
    report_events = by_type.get(AssessmentEventType.RECOMMENDATION_REPORT_GENERATED, [])
    assert len(report_events) == 1
    assert report_events[0].topic_id is None  # report-level, not single-topic (data-model.md)

    # One row per flagged topic.
    assert len(by_type.get(AssessmentEventType.WEAK_AREA_FLAGGED, [])) == weak_area_count

    # One row per suggestion -- always paired 1:1 with a flag (FR-006).
    assert len(by_type.get(AssessmentEventType.NEXT_STEP_SUGGESTED, [])) == weak_area_count

    # Every row carries enough payload detail to reconstruct the decision.
    for event in report_events:
        assert "data_sufficiency" in event.payload
        assert "broad_review_needed" in event.payload
        assert event.payload["weak_area_count"] == weak_area_count

    for event in by_type[AssessmentEventType.WEAK_AREA_FLAGGED]:
        assert "p_mastery" in event.payload
        assert event.payload["cited_event_ids"]  # non-empty, SC-002

    for event in by_type[AssessmentEventType.NEXT_STEP_SUGGESTED]:
        assert event.payload["flagged_topic_id"]
        assert event.payload["recommended_topic_id"]
        assert event.payload["reason"] in (
            "direct_practice",
            "prerequisite_gap",
            "prerequisite_not_yet_assessed",
        )
        assert "prerequisite_chain" in event.payload
