"""Integration test: harness runs never touch real learner data and
leave no synthetic rows behind, success or failure (FR-009, FR-014,
SC-006; quickstart.md step 6; corrected post-`/speckit-analyze` finding
G2).

(a) A pre-existing real (`is_demo=False`) `DemoLearnerProfile` row and
its `AssessmentEvent` row are unchanged before vs. after a full harness
run. (b) No `eval-harness-*` rows remain in `demo_learner_profiles`,
`mastery_states`, or `assessment_events` afterward -- verified by total
table-count restoration, since `MasteryState`/`AssessmentEvent` carry no
name field of their own to filter by prefix directly.
"""

from src.models.assessment_event import AssessmentEvent
from src.models.demo_learner_profile import DemoLearnerProfile
from src.models.enums import AssessmentEventType
from src.models.mastery_state import MasteryState
from src.services.audit_log.writer import record_event
from src.services.evaluation import run_harness
from src.services.evaluation.conditions import EVAL_HARNESS_LEARNER_PREFIX


def test_real_data_untouched_and_synthetic_rows_cleaned_up(
    database_available, db_session, algebra_subject, tmp_path
):
    real_learner = DemoLearnerProfile(display_name="Real Learner", is_demo=False)
    db_session.add(real_learner)
    db_session.flush()
    record_event(
        db_session,
        learner_id=real_learner.learner_id,
        event_type=AssessmentEventType.RECOMMENDATION_REPORT_GENERATED,
        subject_id=algebra_subject.subject_id,
        topic_id=None,
        payload={"pre_existing": True},
    )
    db_session.commit()

    real_learner_count_before = (
        db_session.query(DemoLearnerProfile).filter(DemoLearnerProfile.is_demo.is_(False)).count()
    )
    mastery_state_count_before = db_session.query(MasteryState).count()
    assessment_event_count_before = db_session.query(AssessmentEvent).count()

    run_harness.main(
        ["--subject", algebra_subject.subject_id, "--profile", "cold-start", "--seed", "1"],
        report_path=tmp_path / "latest.json",
    )

    db_session.expire_all()

    real_learner_count_after = (
        db_session.query(DemoLearnerProfile).filter(DemoLearnerProfile.is_demo.is_(False)).count()
    )
    assert real_learner_count_after == real_learner_count_before

    real_event_after = (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.learner_id == real_learner.learner_id)
        .one()
    )
    assert real_event_after.payload == {"pre_existing": True}

    leftover_learners = (
        db_session.query(DemoLearnerProfile)
        .filter(DemoLearnerProfile.display_name.like(f"{EVAL_HARNESS_LEARNER_PREFIX}%"))
        .count()
    )
    assert leftover_learners == 0

    # Total counts back to their pre-run baseline proves no synthetic
    # MasteryState/AssessmentEvent rows survive -- these tables carry no
    # name field to filter by prefix directly.
    assert db_session.query(MasteryState).count() == mastery_state_count_before
    assert db_session.query(AssessmentEvent).count() == assessment_event_count_before
