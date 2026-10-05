"""Integration test: a brand-new subject with zero trained-classifier
history degrades gracefully, exactly as Milestone 11's existing
missing-artifact case already guarantees (spec 040 User Story 1,
FR-008, tasks.md T008).

`_load_classifier` is NOT mocked here: `algebra-2`/`physics` genuinely
have no `classifier.joblib` on disk under `misconception_models/` (no
training has ever run for either), the real, honest cold-start case --
only `embed_answer` is mocked (external Voyage API call, irrelevant to
what this test verifies). Scoped to `physics` alone, not both new
subjects: the code path is identical regardless of which `subject_id`
is missing an artifact (`_load_classifier`'s `path.is_file()` check
does not special-case any subject), so a second subject would be a
redundant assertion, not additional coverage.

The semantic/guardrail-cache half of FR-008 ("every call is a real
miss until history accumulates") is not separately asserted here --
it's definitionally true for content that has never been seen before,
not a behavior this test needs to exercise.
"""

from unittest.mock import patch

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.services.misconception.classify import run_classification_batch
from tests.integration.misconception.scenarios import record_qualifying_wrong_answers


def test_new_subject_with_no_trained_classifier_is_skipped_not_errored(
    db_session, demo_learner, physics_subject
):
    record_qualifying_wrong_answers(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=physics_subject.subject_id,
        topic_id="work-energy-and-power",
        responses=[
            "The object's kinetic energy increased by the applied force amount.",
            "Work equals the force applied, nothing else matters.",
            "I just added the force and the distance together.",
        ],
    )

    with patch("src.services.misconception.classify.embed_answer", return_value=[0.1, 0.2, 0.3]):
        classified_count = run_classification_batch(db_session)  # must not raise

    assert classified_count == 0

    events = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.event_type == AssessmentEventType.MISCONCEPTION_CLASSIFIED)
        .all()
    )
    assert events == []
