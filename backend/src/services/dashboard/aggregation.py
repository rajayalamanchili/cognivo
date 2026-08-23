"""Instructor dashboard aggregation (FR-008/FR-009, research.md §4).

Fans out to the existing, unmodified `build_weak_area_report` once per
learner enrolled in the requested roster -- no new weak-area
classification logic (Constitution Principle IV). A plain synchronous
loop, not `asyncio.gather`: `build_weak_area_report` makes no LLM/
network call, so N sequential in-process calls for a realistic
30-learner roster is bounded by ordinary DB query latency, not
external I/O (research.md §4). Returns domain objects only -- API
response shaping (byte-for-byte identical to `GET /api/learners/
{learner_id}/recommendations`, SC-001) is `api/routes/recommendation.py`'s
`recommendations_response_from_report`, reused by `api/routes/
instructor_dashboard.py` rather than duplicated here.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.agents.recommendation.agent import WeakAreaReport, build_weak_area_report
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.learner_profile import LearnerProfile


@dataclass(frozen=True)
class LearnerDashboardEntry:
    learner_id: uuid.UUID
    display_name: str
    report: WeakAreaReport


def build_roster_dashboard(db: Session, *, roster: ClassroomRoster) -> list[LearnerDashboardEntry]:
    """One `build_weak_area_report` call per learner currently enrolled
    in `roster` (`display_name` order for a stable listing). A learner
    with insufficient assessment history still gets an entry here --
    `build_weak_area_report` reports that in-band via `data_sufficiency`
    (FR-009), it never raises."""
    enrolled_learners = (
        db.query(LearnerProfile)
        .join(Enrollment, Enrollment.learner_id == LearnerProfile.learner_id)
        .filter(Enrollment.roster_id == roster.roster_id)
        .order_by(LearnerProfile.display_name)
        .all()
    )
    return [
        LearnerDashboardEntry(
            learner_id=learner.learner_id,
            display_name=learner.display_name,
            report=build_weak_area_report(
                db, learner_id=learner.learner_id, subject_id=roster.subject_id
            ),
        )
        for learner in enrolled_learners
    ]
