"""Integration tests: `run_classification_batch`'s bounded-execution-time
mitigations (spec 013 research.md §3, post-review 2026-09-01) --
Principle IX requires this cron route stay inside its shared 30s Vercel
`maxDuration`.

- `MAX_PAIRS_PER_RUN` caps how many pairs one run processes, oldest-
  qualifying-evidence-first, deferring the rest to a later run via the
  existing watermark (never losing them).
- `_load_classifier` deserializes a subject's `classifier.joblib` at
  most once per run, via a cache shared across every pair in that run.
"""

from unittest.mock import Mock, patch

import numpy as np

import src.services.misconception.classify as classify_module
from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.models.learner_profile import LearnerProfile
from src.services.misconception.classify import run_classification_batch
from tests.integration.misconception.scenarios import record_qualifying_wrong_answers


def _fake_model(class_labels, probabilities_per_row):
    model = Mock()
    model.classes_ = class_labels
    model.predict_proba = Mock(return_value=np.array(probabilities_per_row))
    return model


def test_batch_size_cap_defers_excess_pairs_to_a_later_run(
    db_session, demo_learner, algebra_subject, biology_subject, monkeypatch
):
    monkeypatch.setattr(classify_module, "MAX_PAIRS_PER_RUN", 1)
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

    fake_algebra_model = _fake_model(
        class_labels=["swaps-slope-and-y-intercept", "treats-y-intercept-as-x-value"],
        probabilities_per_row=[[0.9, 0.1]] * 3,
    )
    fake_biology_model = _fake_model(
        class_labels=[
            "reverses-hypertonic-hypotonic-water-flow",
            "assumes-all-membrane-transport-requires-energy",
        ],
        probabilities_per_row=[[0.9, 0.1]] * 3,
    )

    def _load_classifier_side_effect(subject_id, cache=None):
        return fake_algebra_model if subject_id == "algebra-1" else fake_biology_model

    with (
        patch(
            "src.services.misconception.classify.embed_answer", return_value=[0.1, 0.2, 0.3]
        ),
        patch(
            "src.services.misconception.classify._load_classifier",
            side_effect=_load_classifier_side_effect,
        ),
    ):
        first_run_count = run_classification_batch(db_session)
        second_run_count = run_classification_batch(db_session)

    assert first_run_count == 1
    assert second_run_count == 1

    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .order_by(AssessmentEvent.created_at)
        .all()
    )
    assert len(events) == 2
    # algebra-1's evidence was recorded first, so it's older and must be
    # processed first under the cap.
    assert events[0].subject_id == "algebra-1"
    assert events[1].subject_id == "biology"


def test_classifier_loaded_once_per_subject_across_a_batch_run(db_session, algebra_subject):
    learner_a = LearnerProfile(display_name="Test Learner A", is_demo=True)
    learner_b = LearnerProfile(display_name="Test Learner B", is_demo=True)
    db_session.add_all([learner_a, learner_b])
    db_session.commit()

    for learner in (learner_a, learner_b):
        record_qualifying_wrong_answers(
            db_session,
            learner_id=learner.learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id="graphing-linear-equations",
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
        patch(
            "src.services.misconception.classify.joblib.load", return_value=fake_model
        ) as mock_load,
    ):
        classified_count = run_classification_batch(db_session)

    assert classified_count == 2
    mock_load.assert_called_once()
