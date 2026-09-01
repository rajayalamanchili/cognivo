"""Integration test: `run_classification_batch` only (re)classifies
pairs with newly-qualifying free-text evidence since the last run --
a pair with no new evidence must not produce a second, duplicate
`misconception_classified` event on the next scheduled run
(spec 013 research.md §3, contracts/api.md: "since the last run").
"""

from unittest.mock import Mock, patch

import numpy as np

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.services.misconception.classify import run_classification_batch
from tests.integration.misconception.scenarios import (
    record_free_text_answer,
    record_qualifying_wrong_answers,
)


def _fake_model(class_labels, probabilities_per_row):
    model = Mock()
    model.classes_ = class_labels
    model.predict_proba = Mock(return_value=np.array(probabilities_per_row))
    return model


def test_second_run_with_no_new_evidence_does_not_reclassify(
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
        first_run_count = run_classification_batch(db_session)
        second_run_count = run_classification_batch(db_session)

    assert first_run_count == 1
    assert second_run_count == 0

    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .all()
    )
    assert len(events) == 1


def test_subsequent_correct_answer_does_not_retrigger_reclassification(
    db_session, demo_learner, algebra_subject
):
    """A correct free-text answer submitted after classification changes
    nothing `classify_learner_topic` would see (it only ever considers
    incorrect answers as evidence) -- it must not advance the watermark
    and trigger a duplicate re-classification."""
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
        first_run_count = run_classification_batch(db_session)

        record_free_text_answer(
            db_session,
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            response="The slope is 2 and the y-intercept is 5.",
            correct=True,
            prior_p_mastery=0.2,
            posterior_p_mastery=0.3,
        )
        db_session.commit()
        second_run_count = run_classification_batch(db_session)

    assert first_run_count == 1
    assert second_run_count == 0

    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .all()
    )
    assert len(events) == 1


def test_new_evidence_after_classification_triggers_reclassification(
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
        first_run_count = run_classification_batch(db_session)

        record_qualifying_wrong_answers(
            db_session,
            learner_id=learner_id,
            subject_id=subject_id,
            topic_id=topic_id,
            responses=["The slope is negative four."],
        )
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
    assert len(events[1].payload["cited_event_ids"]) == 4
