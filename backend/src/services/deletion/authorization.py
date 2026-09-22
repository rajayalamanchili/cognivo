"""spec 020 contracts/api.md's "who may request deletion of what" table
(FR-001): a guardian may target themself or their own linked learner; an
instructor may target themself or a learner enrolled in one of their own
rosters. Everything else -- including a `demo_instructor` session, which
never has real-account authority (FR-007, research.md R6) -- is denied.

Takes `SessionClaims` directly rather than a resolved account row so a
`demo_instructor` session is rejected without an extra DB lookup first.
"""

import uuid

from sqlalchemy.orm import Session

from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enums import DeletionTargetType
from src.models.learner_profile import LearnerProfile
from src.services.auth.tokens import SessionClaims


def can_request_deletion(
    requester_claims: SessionClaims,
    target_type: DeletionTargetType,
    target_id: uuid.UUID,
    db: Session,
) -> bool:
    if requester_claims.account_type == "guardian":
        if target_type == DeletionTargetType.GUARDIAN:
            return target_id == requester_claims.account_id
        if target_type == DeletionTargetType.LEARNER:
            learner = db.get(LearnerProfile, target_id)
            return learner is not None and learner.guardian_id == requester_claims.account_id
        return False

    if requester_claims.account_type == "instructor":
        if target_type == DeletionTargetType.INSTRUCTOR:
            return target_id == requester_claims.account_id
        if target_type == DeletionTargetType.LEARNER:
            enrollment = (
                db.query(Enrollment)
                .join(ClassroomRoster, Enrollment.roster_id == ClassroomRoster.roster_id)
                .filter(
                    ClassroomRoster.instructor_id == requester_claims.account_id,
                    Enrollment.learner_id == target_id,
                )
                .first()
            )
            return enrollment is not None
        return False

    return False
