#!/usr/bin/env python3
"""Resets the demo instructor and every demo learner to their
known-good seeded state (FR-015, `/speckit-analyze` finding F4).

Deletes every row scoped to a demo learner (generated questions,
assessment events, mastery state, quiz sessions, roster enrollments/
requests) and every roster the demo instructor owns (cascading to that
roster's own enrollments/requests) -- then re-seeds the demo learner
and demo instructor profile rows themselves via `seed_demo_learner.py`/
`seed_demo_instructor.py`'s own idempotent functions. Those two
functions only create a row if one with the matching `display_name`
doesn't already exist, so this reset never touches the profile rows'
own fields (there's no path to mutate `display_name` post-creation
anyway) -- only their dependent data.

Run on a schedule via Vercel Cron (tech-stack.md's Demo account reset
row, "e.g. daily") -- see `vercel.json`.

Usage: python scripts/reset_demo_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_demo_instructor import seed_demo_instructor  # noqa: E402
from scripts.seed_demo_learner import seed_demo_learner  # noqa: E402
from src.db import get_sessionmaker  # noqa: E402
from src.models.assessment_event import AssessmentEvent  # noqa: E402
from src.models.classroom_roster import ClassroomRoster  # noqa: E402
from src.models.demo_instructor_profile import DemoInstructorProfile  # noqa: E402
from src.models.enrollment import Enrollment  # noqa: E402
from src.models.enrollment_request import EnrollmentRequest  # noqa: E402
from src.models.generated_question import GeneratedQuestion  # noqa: E402
from src.models.learner_profile import LearnerProfile  # noqa: E402
from src.models.mastery_state import MasteryState  # noqa: E402
from src.models.quiz_session import QuizSession  # noqa: E402


def reset_demo_data() -> None:
    session_local = get_sessionmaker()
    with session_local() as db:
        demo_learner_ids = [
            row.learner_id
            for row in db.query(LearnerProfile).filter(LearnerProfile.is_demo.is_(True)).all()
        ]
        demo_instructor_ids = [row.instructor_id for row in db.query(DemoInstructorProfile).all()]

        if demo_learner_ids:
            db.query(GeneratedQuestion).filter(
                GeneratedQuestion.learner_id.in_(demo_learner_ids)
            ).delete(synchronize_session=False)
            db.query(AssessmentEvent).filter(
                AssessmentEvent.learner_id.in_(demo_learner_ids)
            ).delete(synchronize_session=False)
            db.query(MasteryState).filter(MasteryState.learner_id.in_(demo_learner_ids)).delete(
                synchronize_session=False
            )
            db.query(QuizSession).filter(QuizSession.learner_id.in_(demo_learner_ids)).delete(
                synchronize_session=False
            )
            db.query(Enrollment).filter(Enrollment.learner_id.in_(demo_learner_ids)).delete(
                synchronize_session=False
            )
            db.query(EnrollmentRequest).filter(
                EnrollmentRequest.learner_id.in_(demo_learner_ids)
            ).delete(synchronize_session=False)

        if demo_instructor_ids:
            demo_roster_ids = [
                row.roster_id
                for row in db.query(ClassroomRoster)
                .filter(ClassroomRoster.instructor_id.in_(demo_instructor_ids))
                .all()
            ]
            if demo_roster_ids:
                db.query(Enrollment).filter(Enrollment.roster_id.in_(demo_roster_ids)).delete(
                    synchronize_session=False
                )
                db.query(EnrollmentRequest).filter(
                    EnrollmentRequest.roster_id.in_(demo_roster_ids)
                ).delete(synchronize_session=False)
                db.query(ClassroomRoster).filter(
                    ClassroomRoster.roster_id.in_(demo_roster_ids)
                ).delete(synchronize_session=False)

        db.commit()

    # Idempotent -- reuses the existing profile row by display_name,
    # only creates one if somehow missing entirely.
    seed_demo_learner()
    seed_demo_instructor()


def main() -> None:
    reset_demo_data()
    print("demo data reset to known-good seeded state")


if __name__ == "__main__":
    sys.exit(main())
