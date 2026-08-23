"""Integration test: running `reset_demo_data.py` against a demo state
that's been mutated (e.g. the demo instructor's roster has extra
enrollments, the demo learner has extra assessment events) restores it
to exactly the seeded baseline (SC-005, T057c).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import uuid

import pytest

from scripts import seed_demo_instructor as seed_demo_instructor_module
from scripts import seed_demo_learner as seed_demo_learner_module
from scripts.reset_demo_data import reset_demo_data
from src.models.assessment_event import AssessmentEvent
from src.models.classroom_roster import ClassroomRoster
from src.models.demo_instructor_profile import DemoInstructorProfile
from src.models.enrollment import Enrollment
from src.models.enums import AuthorizedByType, DifficultyBand, EnrollmentMode, QuestionType
from src.models.generated_question import GeneratedQuestion
from src.models.learner_profile import LearnerProfile
from src.models.mastery_state import MasteryState

seed_demo_instructor = seed_demo_instructor_module.seed_demo_instructor
seed_demo_learner = seed_demo_learner_module.seed_demo_learner
DEMO_INSTRUCTOR_NAME = seed_demo_instructor_module.DEFAULT_DISPLAY_NAME
DEMO_LEARNER_NAME = seed_demo_learner_module.DEFAULT_DISPLAY_NAME

pytestmark = pytest.mark.usefixtures("database_available")


def test_reset_restores_seeded_baseline_after_mutation(db_session, algebra_subject):
    demo_learner = seed_demo_learner()
    demo_instructor = seed_demo_instructor()

    # Mutate: extra roster + enrollment for the demo instructor, extra
    # assessment history for the demo learner.
    other_learner = LearnerProfile(display_name="Not The Demo Learner", is_demo=False)
    db_session.add(other_learner)
    db_session.flush()

    roster = ClassroomRoster(
        instructor_id=demo_instructor.instructor_id,
        subject_id=algebra_subject.subject_id,
        enrollment_mode=EnrollmentMode.OPEN,
        join_code=f"DEMO-{uuid.uuid4().hex[:4].upper()}",
    )
    db_session.add(roster)
    db_session.flush()

    db_session.add(
        Enrollment(
            learner_id=other_learner.learner_id,
            roster_id=roster.roster_id,
            authorized_by_type=AuthorizedByType.GUARDIAN,
            authorized_by_id=uuid.uuid4(),
        )
    )

    question = GeneratedQuestion(
        learner_id=demo_learner.learner_id,
        subject_id=algebra_subject.subject_id,
        topic_id=algebra_subject.topics[0].topic_id,
        difficulty=DifficultyBand.EASY,
        question_type=QuestionType.MULTIPLE_CHOICE,
        stem="mutated demo question",
        options=["a", "b", "c", "d"],
        answer_key={"correct_index": 0},
    )
    db_session.add(question)
    db_session.add(
        MasteryState(
            learner_id=demo_learner.learner_id,
            subject_id=algebra_subject.subject_id,
            topic_id=algebra_subject.topics[0].topic_id,
            p_mastery=0.9,
            update_count=5,
        )
    )
    db_session.commit()

    mutated_roster_count = (
        db_session.query(ClassroomRoster)
        .filter(ClassroomRoster.instructor_id == demo_instructor.instructor_id)
        .count()
    )
    assert mutated_roster_count == 1
    mutated_mastery_count = (
        db_session.query(MasteryState)
        .filter(MasteryState.learner_id == demo_learner.learner_id)
        .count()
    )
    assert mutated_mastery_count == 1

    reset_demo_data()

    db_session.expire_all()

    # Demo profile rows themselves are untouched (same id, same fields).
    learner_after = db_session.get(LearnerProfile, demo_learner.learner_id)
    assert learner_after is not None
    assert learner_after.display_name == DEMO_LEARNER_NAME
    assert learner_after.is_demo is True

    instructor_after = db_session.get(DemoInstructorProfile, demo_instructor.instructor_id)
    assert instructor_after is not None
    assert instructor_after.display_name == DEMO_INSTRUCTOR_NAME
    assert instructor_after.is_demo is True

    # Every roster/enrollment/mastery/question/event tied to the demo
    # instructor or demo learner is gone.
    assert (
        db_session.query(ClassroomRoster)
        .filter(ClassroomRoster.instructor_id == demo_instructor.instructor_id)
        .count()
        == 0
    )
    assert (
        db_session.query(MasteryState)
        .filter(MasteryState.learner_id == demo_learner.learner_id)
        .count()
        == 0
    )
    assert (
        db_session.query(GeneratedQuestion)
        .filter(GeneratedQuestion.learner_id == demo_learner.learner_id)
        .count()
        == 0
    )
    assert (
        db_session.query(AssessmentEvent)
        .filter(AssessmentEvent.learner_id == demo_learner.learner_id)
        .count()
        == 0
    )
    assert (
        db_session.query(Enrollment).filter(Enrollment.roster_id == roster.roster_id).count() == 0
    )

    # The unrelated learner (not the demo learner) is untouched.
    assert db_session.get(LearnerProfile, other_learner.learner_id) is not None
