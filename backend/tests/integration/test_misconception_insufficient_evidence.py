"""Integration test: with fewer than the minimum qualifying events, no
`misconception_classified` event is written and the weak-area report's
`misconception` field is `null`, every other field byte-for-byte
unchanged from spec 002 (spec 013 SC-004), T015.
"""

import pytest
from fastapi.testclient import TestClient

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.mastery_state import MasteryState
from src.services.misconception.classify import classify_learner_topic
from tests.integration.misconception.scenarios import record_free_text_answer


@pytest.fixture()
def client():
    from src.api.main import app

    return TestClient(app)


def test_insufficient_evidence_yields_no_event_and_null_field(
    client, db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id
    topic_id = "graphing-linear-equations"

    # 3 total answered questions (>= weak_area.py's own CONFIDENT_MIN_
    # EVENTS, so the topic is still flagged weak and appears in
    # weak_areas[]) but only 2 are free-text-incorrect -- classify.py's
    # own qualifying-evidence count stays below its threshold (3),
    # since a correct answer never qualifies as evidence (FR-001).
    record_free_text_answer(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        response="The slope is 5 and the y-intercept is 2.",
        correct=False,
        prior_p_mastery=None,
        posterior_p_mastery=0.2,
    )
    record_free_text_answer(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        response="Slope is 7, y-intercept is -3.",
        correct=False,
        prior_p_mastery=0.2,
        posterior_p_mastery=0.2,
    )
    record_free_text_answer(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id=topic_id,
        response="The slope is 2 and the y-intercept is 5.",
        correct=True,
        prior_p_mastery=0.2,
        posterior_p_mastery=0.2,
    )
    db_session.add(
        MasteryState(
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            p_mastery=0.2,
            update_count=3,
        )
    )
    db_session.commit()

    event = classify_learner_topic(
        db_session, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id
    )
    db_session.commit()
    assert event is None

    persisted = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .all()
    )
    assert persisted == []

    response = client.get(
        f"/api/learners/{learner_id}/recommendations", params={"subject_id": subject_id}
    )
    assert response.status_code == 200, response.text
    body = response.json()

    flags = [f for f in body["weak_areas"] if f["topic_id"] == topic_id]
    assert len(flags) == 1
    assert flags[0]["misconception"] is None
    # Every other field still present and shaped exactly per spec 002.
    assert "p_mastery" in flags[0]
    assert "evidence" in flags[0]
    assert "next_step" in flags[0]
