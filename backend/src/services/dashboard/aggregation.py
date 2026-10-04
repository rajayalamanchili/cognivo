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
from src.services.standards.coverage import StandardCoverageEntry, compute_standards_coverage


@dataclass(frozen=True)
class LearnerDashboardEntry:
    learner_id: uuid.UUID
    display_name: str
    report: WeakAreaReport
    # Spec 038 FR-004 -- same shape/derivation as the guardian-facing
    # mastery-state surface (api/routes/mastery.py), via the same shared
    # compute_standards_coverage() call.
    standards: tuple[StandardCoverageEntry, ...]


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
            standards=tuple(
                compute_standards_coverage(
                    db, learner_id=learner.learner_id, subject_id=roster.subject_id
                )
            ),
        )
        for learner in enrolled_learners
    ]


@dataclass(frozen=True)
class RosterStandardSummaryEntry:
    framework: str
    code: str
    title: str
    met_count: int
    total_count: int


def build_roster_standards_summary(
    entries: list[LearnerDashboardEntry],
) -> list[RosterStandardSummaryEntry]:
    """Spec 038 FR-005, User Story 2 -- combines each already-computed
    `LearnerDashboardEntry.standards` (no new query, no new mastery
    computation) into one count per distinct `(framework, code)` across
    the roster. `total_count` is the roster's total enrolled learners,
    not total tagged topics. Empty for an empty roster or a subject with
    zero `StandardsTag` rows -- every enrolled learner's `standards` is
    computed against the same subject, so they all carry the same set of
    `(framework, code)` keys (research.md Decision 2's title-consistency
    guarantee means whichever entry's title is read, it's correct)."""
    title_by_code: dict[tuple[str, str], str] = {}
    met_count_by_code: dict[tuple[str, str], int] = {}
    for entry in entries:
        for standard in entry.standards:
            key = (standard.framework, standard.code)
            title_by_code[key] = standard.title
            met_count_by_code.setdefault(key, 0)
            if standard.status == "met":
                met_count_by_code[key] += 1

    total_count = len(entries)
    return [
        RosterStandardSummaryEntry(
            framework=framework,
            code=code,
            title=title_by_code[(framework, code)],
            met_count=met_count,
            total_count=total_count,
        )
        for (framework, code), met_count in met_count_by_code.items()
    ]
