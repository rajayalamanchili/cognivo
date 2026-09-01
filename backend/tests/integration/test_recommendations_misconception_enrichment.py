"""Integration test: `GET /api/learners/{id}/recommendations` returns a
populated, evidence-bearing `misconception` field on the matching
`weak_areas[]` entry when a recent `misconception_classified` event
exists (spec 013 contracts/api.md, SC-003), T014.

Simulates classification having already run (via `record_event`
directly) rather than re-exercising `classify_learner_topic` -- this
test is about the *read* side (`weak_area.py`/the endpoint), which
never invokes the classifier itself (research.md §3).
"""

import pytest
from fastapi.testclient import TestClient

from src.models.enums import AssessmentEventType
from src.services.audit_log.writer import record_event
from tests.integration.misconception.scenarios import record_qualifying_wrong_answers


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


def test_recommendations_response_includes_populated_misconception_field(
    client, db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id
    topic_id = "graphing-linear-equations"

    recorded = record_qualifying_wrong_answers(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        responses=[
            "The slope is 5 and the y-intercept is 2.",
            "Slope is 7, y-intercept is -3.",
            "The slope is -1.",
        ],
    )
    cited_event_ids = [str(answer_event.event_id) for _, answer_event, _ in recorded]

    record_event(
        db_session,
        learner_id=learner_id,
        event_type=AssessmentEventType.MISCONCEPTION_CLASSIFIED,
        subject_id=subject_id,
        topic_id=topic_id,
        payload={
            "misconception_id": "swaps-slope-and-y-intercept",
            "confidence": 0.82,
            "cited_event_ids": cited_event_ids,
            "classifier_version": "v1",
        },
    )
    db_session.commit()

    response = client.get(
        f"/api/learners/{learner_id}/recommendations", params={"subject_id": subject_id}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    flags = [f for f in body["weak_areas"] if f["topic_id"] == topic_id]
    assert len(flags) == 1
    misconception = flags[0]["misconception"]
    assert misconception is not None
    assert misconception["misconception_id"] == "swaps-slope-and-y-intercept"
    assert misconception["confidence"] == pytest.approx(0.82)
    assert misconception["description"]
    assert len(misconception["evidence"]) == 3
    for citation in misconception["evidence"]:
        assert citation["event_id"]
        assert citation["question_stem"]

    # Every other WeakAreaFlag field is unchanged from spec 002's shape.
    assert flags[0]["p_mastery"] == pytest.approx(0.2)
    assert flags[0]["next_step"]["recommended_topic_id"]
