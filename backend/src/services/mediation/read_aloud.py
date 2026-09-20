"""Read-aloud eligibility (spec 019 FR-001/FR-003, research.md Decision 1).

`is_read_aloud_eligible` is a pure function, deliberately DB-free, with
no dependency on User Story 2's mediation-tier logic (spec 019
tasks.md: the three user stories share no backend surface area on
purpose). `resolve_read_aloud_eligible` is the one shared DB-aware
wrapper both `questions.py` and `quiz.py` call, so the `GradeProgress`
lookup isn't duplicated across route modules.
"""

import uuid

from sqlalchemy.orm import Session

from src.models.grade_progress import GradeProgress


def is_read_aloud_eligible(unlocked_grade: int | None) -> bool:
    """Grades 1-2 only (FR-001/FR-003). `None` (no `GradeProgress` row --
    an ungraded subject, or a subject the learner hasn't been placed
    into yet) is not eligible, matching FR-013's "entirely unaffected"
    guarantee for ungraded subjects."""
    return unlocked_grade is not None and unlocked_grade <= 2


def resolve_read_aloud_eligible(db: Session, *, learner_id: uuid.UUID, subject_id: str) -> bool:
    """FR-011: derived live from `GradeProgress` on every call, never a
    separately stored copy of grade."""
    progress = (
        db.query(GradeProgress)
        .filter(GradeProgress.learner_id == learner_id, GradeProgress.subject_id == subject_id)
        .first()
    )
    return is_read_aloud_eligible(progress.unlocked_grade if progress else None)
