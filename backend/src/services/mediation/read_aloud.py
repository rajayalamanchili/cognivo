"""Read-aloud eligibility (spec 019 FR-001/FR-003, research.md Decision 1).

Originally gated to grades 1-2; the grade restriction was removed
(Clarifications, 2026-10-03) -- read-aloud is now unconditional for
every learner, every grade, every subject. Both functions are kept
(rather than inlining `True` at each of the four call sites) so a
future eligibility rule has one place to land, same as before.
"""

import uuid

from sqlalchemy.orm import Session


def is_read_aloud_eligible(unlocked_grade: int | None) -> bool:
    """Unconditional (Clarifications, 2026-10-03). `unlocked_grade` is
    kept as a parameter for call-site compatibility but no longer
    consulted."""
    return True


def resolve_read_aloud_eligible(db: Session, *, learner_id: uuid.UUID, subject_id: str) -> bool:
    """Unconditional (Clarifications, 2026-10-03) -- no longer queries
    `GradeProgress`. Signature kept for call-site compatibility."""
    return True
