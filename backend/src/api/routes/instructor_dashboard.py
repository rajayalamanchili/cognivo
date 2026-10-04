"""Instructor dashboard endpoint (contracts/api.md "Dashboard" section,
User Story 3).
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import ForbiddenError, NotFoundError
from src.api.routes.mastery import StandardCoverageOut, standards_out_from_coverage
from src.api.routes.recommendation import (
    RecommendationsResponse,
    recommendations_response_from_report,
)
from src.db import get_db
from src.models.classroom_roster import ClassroomRoster
from src.services.auth.dependencies import InstructorAccount, current_instructor
from src.services.dashboard.aggregation import build_roster_dashboard, build_roster_standards_summary

router = APIRouter()


class DashboardLearnerOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    recommendations: RecommendationsResponse
    # Spec 038 FR-004 -- identical in shape/derivation to the
    # guardian-facing mastery-state surface's `standards` field.
    standards: list[StandardCoverageOut]


class RosterStandardSummaryOut(BaseModel):
    framework: str
    code: str
    title: str
    met_count: int
    total_count: int


class DashboardOut(BaseModel):
    roster_id: uuid.UUID
    subject_id: str
    learners: list[DashboardLearnerOut]
    # Spec 038 FR-005, User Story 2 -- one entry per distinct
    # (framework, code) across the roster; empty when the subject has
    # zero StandardsTag rows (not an empty-table render, FR-006).
    standards_summary: list[RosterStandardSummaryOut]


@router.get("/api/rosters/{roster_id}/dashboard", response_model=DashboardOut)
def get_roster_dashboard(
    roster_id: uuid.UUID,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> DashboardOut:
    roster = db.get(ClassroomRoster, roster_id)
    if roster is None:
        raise NotFoundError("unknown roster_id")
    if roster.instructor_id != instructor.instructor_id:
        raise ForbiddenError("not_roster_owner")

    entries = build_roster_dashboard(db, roster=roster)
    standards_summary = build_roster_standards_summary(entries)

    return DashboardOut(
        roster_id=roster.roster_id,
        subject_id=roster.subject_id,
        learners=[
            DashboardLearnerOut(
                learner_id=entry.learner_id,
                display_name=entry.display_name,
                recommendations=recommendations_response_from_report(entry.report),
                standards=standards_out_from_coverage(entry.standards),
            )
            for entry in entries
        ],
        standards_summary=[
            RosterStandardSummaryOut(
                framework=s.framework,
                code=s.code,
                title=s.title,
                met_count=s.met_count,
                total_count=s.total_count,
            )
            for s in standards_summary
        ],
    )
