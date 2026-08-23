"""Demo-instructor entry point (contracts/api.md "Demo entry points"
section, extending Milestone 1's `GET /api/demo-learner` pattern to
instructors, spec 010 FR-014).

Requires no session cookie to *call* -- same public, no-auth pattern as
`GET /api/demo-learner`. Unlike that endpoint, this one also issues a
session cookie on response (`/speckit-clarify` with the user): a visitor
who calls this can then actually browse `/instructor/rosters`,
`/instructor/dashboard`, and `/instructor/review` as the seeded demo
instructor, not just look up its id/name. The session claim uses the
distinct `demo_instructor` account type (`tokens.py`) so
`current_instructor` resolves it against `DemoInstructorProfile`, never
`RealInstructorAccount`.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.errors import NotFoundError
from src.db import get_db
from src.models.demo_instructor_profile import DemoInstructorProfile
from src.services.auth.tokens import issue_token, set_session_cookie

router = APIRouter()


class DemoInstructorOut(BaseModel):
    instructor_id: uuid.UUID
    display_name: str


@router.get("/api/demo-instructor", response_model=DemoInstructorOut)
def get_demo_instructor_route(
    response: Response, db: Session = Depends(get_db)
) -> DemoInstructorOut:
    instructor = db.query(DemoInstructorProfile).order_by(DemoInstructorProfile.created_at).first()
    if instructor is None:
        raise NotFoundError(
            "no demo instructor profile seeded -- run scripts/seed_demo_instructor.py"
        )

    token = issue_token(account_type="demo_instructor", account_id=instructor.instructor_id)
    set_session_cookie(response, token)

    return DemoInstructorOut(
        instructor_id=instructor.instructor_id, display_name=instructor.display_name
    )
