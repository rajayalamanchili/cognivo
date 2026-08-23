"""Content-review queue endpoints (contracts/api.md "Content review"
section, User Story 4).
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db
from src.services.auth.dependencies import InstructorAccount, current_instructor
from src.services.content_review.resolution import (
    ResolutionAction,
    list_flagged_questions,
    resolve_flagged_question,
)

router = APIRouter()


class FlaggedQuestionOut(BaseModel):
    question_id: uuid.UUID
    learner_id: uuid.UUID
    roster_id: uuid.UUID
    stem: str
    flagged_reason: str | None
    flagged_at: str


class ListFlaggedOut(BaseModel):
    flagged: list[FlaggedQuestionOut]


@router.get("/api/content-review/flagged", response_model=ListFlaggedOut)
def list_flagged_route(
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> ListFlaggedOut:
    entries = list_flagged_questions(db, instructor_id=instructor.instructor_id)
    return ListFlaggedOut(
        flagged=[
            FlaggedQuestionOut(
                question_id=entry.question_id,
                learner_id=entry.learner_id,
                roster_id=entry.roster_id,
                stem=entry.stem,
                flagged_reason=entry.flagged_reason,
                flagged_at=entry.flagged_at.isoformat(),
            )
            for entry in entries
        ]
    )


class ResolveIn(BaseModel):
    action: ResolutionAction


class ResolveOut(BaseModel):
    question_id: uuid.UUID
    validation_status: str


@router.post("/api/content-review/{question_id}/resolve", response_model=ResolveOut)
def resolve_route(
    question_id: uuid.UUID,
    body: ResolveIn,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> ResolveOut:
    question = resolve_flagged_question(
        db, question_id=question_id, instructor_id=instructor.instructor_id, action=body.action
    )
    return ResolveOut(
        question_id=question.question_id, validation_status=question.validation_status.value
    )
