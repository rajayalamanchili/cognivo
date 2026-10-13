"""Integration test: a brand-new subject with zero trained-classifier
history degrades gracefully, exactly as Milestone 11's existing
missing-artifact case already guarantees (spec 046 User Story 1,
FR-008, tasks.md T012).

Scoped to `chemistry` alone, mirroring
`test_new_subject_cold_start_degradation.py`'s own precedent (scoped to
`physics` alone): `_load_classifier`'s `path.is_file()` check does not
special-case any subject, so exercising a second free-text-capable
subject would be a redundant assertion, not additional coverage.
`elementary-math`/`elementary-science` are deliberately excluded here,
not merely skipped -- they author zero free-text-capable topics at all
(spec.md Edge Cases), so this cold-start scenario (which requires a
free-text answer to classify) cannot occur for them by construction;
that is itself the subject of the separate zero-free-text-topics
assertion in `test_content_artifact_load_stem_catalog_expansion.py`,
not this test.
"""

from unittest.mock import patch

from src.models.assessment_event import AssessmentEvent
from src.models.enums import AssessmentEventType
from src.services.misconception.classify import run_classification_batch
from tests.integration.misconception.scenarios import record_qualifying_wrong_answers


def test_new_subject_with_no_trained_classifier_is_skipped_not_errored(
    db_session, demo_learner, chemistry_subject
):
    record_qualifying_wrong_answers(
        db_session,
        learner_id=demo_learner.learner_id,
        subject_id=chemistry_subject.subject_id,
        topic_id="stoichiometry",
        responses=[
            "I just multiplied the grams given without converting to moles first.",
            "The limiting reactant is whichever one is listed first in the equation.",
            "I used the mass ratio from the equation coefficients directly.",
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
