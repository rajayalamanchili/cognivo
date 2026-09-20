"""Exposes a learner's `GradeProgress.unlocked_grade` to the frontend
(spec 019 FR-009/FR-011, research.md Decision 6) -- User Story 3's own
resolver, independent of `read_aloud.py`/`tier.py`, even though all
three ultimately read the same column (the three user stories share no
backend surface area on purpose, tasks.md). Story 3's actual pacing
values are computed client-side (`frontend/src/lib/pacing.ts`); this is
just the raw-grade lookup that makes that possible, since no endpoint
exposed a learner's grade to the client before this feature.
"""

import uuid

from sqlalchemy.orm import Session

from src.models.grade_progress import GradeProgress


def resolve_unlocked_grade(db: Session, *, learner_id: uuid.UUID, subject_id: str) -> int | None:
    """`None` when no `GradeProgress` row exists (an ungraded subject,
    or a subject the learner hasn't been placed into yet) -- the
    frontend pacing lookup treats that the same as an unbounded/late
    band (no checkpoint), matching this feature's "unaffected when no
    grade-band data exists" precedent."""
    progress = (
        db.query(GradeProgress)
        .filter(GradeProgress.learner_id == learner_id, GradeProgress.subject_id == subject_id)
        .first()
    )
    return progress.unlocked_grade if progress else None
