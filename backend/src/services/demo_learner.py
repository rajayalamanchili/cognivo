"""Resolves the Milestone-1 demo learner (spec.md Assumptions: solo-learner
flow only, exactly one seeded `LearnerProfile` with `is_demo: true`, no
auth/session yet -- so endpoints that don't take a `learner_id` path param
resolve it here)."""

from sqlalchemy.orm import Session

from src.api.errors import NotFoundError
from src.models.learner_profile import LearnerProfile


def get_demo_learner(db: Session) -> LearnerProfile:
    learner = (
        db.query(LearnerProfile)
        .filter(LearnerProfile.is_demo.is_(True))
        .order_by(LearnerProfile.created_at)
        .first()
    )
    if learner is None:
        raise NotFoundError("no demo learner profile seeded -- run scripts/seed_demo_learner.py")
    return learner
