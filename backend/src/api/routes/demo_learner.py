"""Demo-learner lookup (not in contracts/api.md's endpoint list).

Every other endpoint that needs a `learner_id` either takes it as a path
param or resolves it server-side (placement start/submit), but nothing
in the placement flow's response ever returns one -- and
`GET /api/learners/{learner_id}/mastery-state` requires it. With no auth
in Milestone 1 (spec.md Assumptions, exactly one seeded
`DemoLearnerProfile`), the frontend needs a way to discover that one
learner's id at all. This is the minimal endpoint that provides it.
"""

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db import get_db
from src.services.demo_learner import get_demo_learner

router = APIRouter()


class DemoLearnerOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str


@router.get("/api/demo-learner", response_model=DemoLearnerOut)
def get_demo_learner_route(db: Session = Depends(get_db)) -> DemoLearnerOut:
    learner = get_demo_learner(db)
    return DemoLearnerOut(learner_id=learner.learner_id, display_name=learner.display_name)
