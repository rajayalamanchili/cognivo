"""Subject-listing endpoint (contracts/api.md, research.md §4) -- lets
the frontend discover which subjects to render without hardcoding
subject ids (Constitution Principle III / SC-005).

Not wrapped in `traced_request()`: no LLM/ADK invocation, matching the
existing `GET /mastery-state`/`GET /recommendations` precedent.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.subject import Subject

router = APIRouter()


class SubjectSummaryOut(BaseModel):
    subject_id: str
    display_name: str


class SubjectsResponse(BaseModel):
    subjects: list[SubjectSummaryOut]


@router.get("/api/subjects", response_model=SubjectsResponse)
def list_subjects(db: Session = Depends(get_db)) -> SubjectsResponse:
    subjects = (
        db.query(Subject)
        .filter(Subject.validated_at.isnot(None))
        .order_by(Subject.subject_id)
        .all()
    )
    return SubjectsResponse(
        subjects=[
            SubjectSummaryOut(subject_id=subject.subject_id, display_name=subject.display_name)
            for subject in subjects
        ]
    )
