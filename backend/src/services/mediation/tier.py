"""Guardian-mediation tier determination (spec 019 FR-004,
research.md Decision 3).

`determine_mediation_tier` is a pure function, deliberately DB-free --
same discipline as `read_aloud.py`'s `is_read_aloud_eligible`. No
dependency on User Story 1's read-aloud logic, even though both key off
the same grade-band boundaries -- the three user stories share no
backend surface area on purpose (tasks.md). `resolve_mediation_tier` is
the one shared DB-aware wrapper every call site (`assignment.py`,
`quiz_assignments.py`) uses, so the `GradeProgress` lookup isn't
duplicated across modules (same precedent as `read_aloud.py`'s
`resolve_read_aloud_eligible`).
"""

import uuid

from sqlalchemy.orm import Session

from src.models.enums import MediationTier
from src.models.grade_progress import GradeProgress


def determine_mediation_tier(unlocked_grade: int | None) -> MediationTier | None:
    """`None` (no `GradeProgress` row -- an ungraded subject, or a
    subject the learner hasn't been placed into yet) is handled
    identically to `CO_PRESENT` at every call site, but is returned as
    `None` here rather than collapsed into `CO_PRESENT` -- so "no tier
    applies" stays a distinguishable, honestly-logged fact (FR-013,
    data-model.md)."""
    if unlocked_grade is None:
        return None
    if unlocked_grade <= 2:
        return MediationTier.CO_PRESENT
    if unlocked_grade <= 5:
        return MediationTier.CHECK_IN
    if unlocked_grade <= 8:
        return MediationTier.OPT_IN_NUDGES
    return MediationTier.INDEPENDENT


def resolve_mediation_tier(
    db: Session, *, learner_id: uuid.UUID, subject_id: str
) -> MediationTier | None:
    """FR-011: derived live from `GradeProgress` on every call, never a
    separately stored copy of grade."""
    progress = (
        db.query(GradeProgress)
        .filter(GradeProgress.learner_id == learner_id, GradeProgress.subject_id == subject_id)
        .first()
    )
    return determine_mediation_tier(progress.unlocked_grade if progress else None)
