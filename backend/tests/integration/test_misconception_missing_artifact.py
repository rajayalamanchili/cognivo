"""Integration test: the classification job encountering a missing/
unloadable `classifier.joblib` for one subject logs and skips that
subject, continuing to classify every other qualifying learner/topic
pair without raising (spec 013 research.md §3), T026.
"""

import numpy as np
from unittest.mock import Mock, patch

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.services.misconception.classify import ClassifierUnavailableError, run_classification_batch
from tests.integration.misconception.scenarios import record_qualifying_wrong_answers


def _fake_model(class_labels, probabilities_per_row):
    model = Mock()
    model.classes_ = class_labels
    model.predict_proba = Mock(return_value=np.array(probabilities_per_row))
    return model


def test_missing_artifact_for_one_subject_does_not_block_others(
    db_session, demo_learner, algebra_subject, biology_subject
):
    learner_id = demo_learner.learner_id

    record_qualifying_wrong_answers(
        db_session,
        learner_id=learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id="graphing-linear-equations",
        responses=[
            "The slope is 5 and the y-intercept is 2.",
            "Slope is 7, y-intercept is -3.",
            "The slope is -1.",
        ],
    )
    record_qualifying_wrong_answers(
        db_session,
        learner_id=learner_id,
        subject_id=biology_subject.subject_id,
        topic_id="cell-transport",
        responses=[
            "Water will move into the cell, from the hypertonic side.",
            "Water moves out of the cell toward the hypotonic side.",
            "The cell will swell because water rushes in from the hypertonic solution.",
        ],
    )

    fake_biology_model = _fake_model(
        class_labels=[
            "reverses-hypertonic-hypotonic-water-flow",
            "assumes-all-membrane-transport-requires-energy",
        ],
        probabilities_per_row=[[0.9, 0.1]] * 3,
    )

    def _load_classifier_side_effect(subject_id):
        if subject_id == "algebra-1":
            raise ClassifierUnavailableError("no trained classifier for subject 'algebra-1'")
        return fake_biology_model

    with (
        patch(
            "src.services.misconception.classify.embed_answer", return_value=[0.1, 0.2, 0.3]
        ),
        patch(
            "src.services.misconception.classify._load_classifier",
            side_effect=_load_classifier_side_effect,
        ),
    ):
        classified_count = run_classification_batch(db_session)

    # algebra-1 failed and was skipped; biology-1 still succeeded.
    assert classified_count == 1

    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .all()
    )
    assert len(events) == 1
    assert events[0].subject_id == "biology"
    assert events[0].payload["misconception_id"] == "reverses-hypertonic-hypotonic-water-flow"
