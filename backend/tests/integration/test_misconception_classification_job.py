"""Integration test: `classify_learner_topic` writes exactly one
`misconception_classified` `AssessmentEvent` with a non-empty
`cited_event_ids` list when a learner/topic pair has sufficient
matching evidence, and its `misconception_id` matches an authored
taxonomy entry -- never an arbitrary label (spec 013 FR-003/FR-004/
FR-008, data-model.md), T013.

`embed_answer`/`_load_classifier` are mocked -- this test exercises the
real DB query/threshold/write path, not a real embedding-provider or
model-file round trip (mirrors this project's existing convention of
mocking the LLM/embedding boundary in fast integration tests).
"""

import numpy as np
from unittest.mock import Mock, patch

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.topic import Topic
from src.services.misconception.classify import classify_learner_topic
from tests.integration.misconception.scenarios import record_qualifying_wrong_answers


def _fake_model(class_labels, probabilities_per_row):
    model = Mock()
    model.classes_ = class_labels
    model.predict_proba = Mock(return_value=np.array(probabilities_per_row))
    return model


def test_classification_job_writes_cited_event_matching_taxonomy(
    db_session, demo_learner, algebra_subject
):
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id
    topic_id = "graphing-linear-equations"

    record_qualifying_wrong_answers(
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

    fake_model = _fake_model(
        class_labels=["swaps-slope-and-y-intercept", "treats-y-intercept-as-x-value"],
        probabilities_per_row=[[0.9, 0.1]] * 3,
    )
    with (
        patch(
            "src.services.misconception.classify.embed_answer", return_value=[0.1, 0.2, 0.3]
        ),
        patch("src.services.misconception.classify._load_classifier", return_value=fake_model),
    ):
        event = classify_learner_topic(
            db_session, learner_id=learner_id, subject_id=subject_id, topic_id=topic_id
        )
    db_session.commit()

    assert event is not None
    assert event.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED
    assert event.payload["misconception_id"] == "swaps-slope-and-y-intercept"
    assert len(event.payload["cited_event_ids"]) == 3
    assert event.payload["classifier_version"] == "v1"

    topic = (
        db_session.query(Topic)
        .filter(Topic.subject_id == subject_id, Topic.topic_id == topic_id)
        .one()
    )
    taxonomy_ids = {m["misconception_id"] for m in topic.skill_definition["misconceptions"]}
    assert event.payload["misconception_id"] in taxonomy_ids

    persisted = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .all()
    )
    assert len(persisted) == 1
