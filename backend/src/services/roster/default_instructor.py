"""The seeded, real "default instructor" account and its always-on,
per-subject roster (spec 043 research.md §5).

Resolved by email (`DEFAULT_INSTRUCTOR_EMAIL`) rather than a dedicated
`is_default_instructor` column -- one indexed lookup per call site is
cheap and needs no new schema (spec.md FR-013's bounded-schema promise).
"""

import logging
import os

from sqlalchemy.orm import Session

from src.models.classroom_roster import ClassroomRoster
from src.models.enums import EnrollmentMode
from src.models.real_instructor_account import RealInstructorAccount
from src.services.roster.enrollment import create_roster, update_roster

logger = logging.getLogger(__name__)


def get_default_instructor(db: Session) -> RealInstructorAccount | None:
    """`None`-safe: an unset env var or no matching row is a normal,
    expected state (e.g. a developer's local DB, CI), never an error."""
    email = os.environ.get("DEFAULT_INSTRUCTOR_EMAIL")
    if not email:
        return None
    normalized = email.strip().lower()
    return (
        db.query(RealInstructorAccount)
        .filter(RealInstructorAccount.email == normalized)
        .one_or_none()
    )


def ensure_default_instructor_roster_for_subject(db: Session, subject_id: str) -> None:
    """Idempotent: a no-op on every call after the first for a given
    `subject_id` (FR-016). No-ops cleanly (not an error) when no default
    instructor is seeded yet, so this is a complete no-op for any
    environment that hasn't set `DEFAULT_INSTRUCTOR_EMAIL`."""
    instructor = get_default_instructor(db)
    if instructor is None:
        logger.info(
            "no default instructor seeded; skipping default roster for subject_id=%r", subject_id
        )
        return

    existing = (
        db.query(ClassroomRoster)
        .filter(
            ClassroomRoster.instructor_id == instructor.instructor_id,
            ClassroomRoster.subject_id == subject_id,
        )
        .one_or_none()
    )
    if existing is not None:
        return

    roster = create_roster(
        db,
        instructor_id=instructor.instructor_id,
        subject_id=subject_id,
        enrollment_mode=EnrollmentMode.OPEN,
    )
    update_roster(
        db,
        roster=roster,
        enrollment_mode=EnrollmentMode.OPEN,
        is_listed=True,
        instructor_display_name=instructor.display_name,
    )
