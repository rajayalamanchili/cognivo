"""Derived assignment-target status (spec 011 data-model.md).

Never stored -- computed at read time from a target's `quiz_session_id`/
linked `QuizSession.status`, the same "derive, never duplicate"
philosophy `QuizSession` itself already uses for its own summary (spec
005 data-model.md). Shared by the guardian-facing assignment list (User
Story 2) and the instructor-facing per-assignment report (User Story 3)
so the two can never report a different status for the same target.
"""

from typing import Literal

from src.models.enums import QuizSessionStatus

AssignmentTargetStatus = Literal["not_started", "in_progress", "completed", "ended_early"]

_QUIZ_SESSION_STATUS_TO_TARGET_STATUS: dict[QuizSessionStatus, AssignmentTargetStatus] = {
    QuizSessionStatus.IN_PROGRESS: "in_progress",
    QuizSessionStatus.COMPLETED: "completed",
    QuizSessionStatus.ENDED_EARLY: "ended_early",
}


def derive_target_status(quiz_session_status: QuizSessionStatus | None) -> AssignmentTargetStatus:
    """`quiz_session_status` is `None` when the target's `quiz_session_id`
    is still `NULL` (the guardian hasn't started the attempt yet)."""
    if quiz_session_status is None:
        return "not_started"
    return _QUIZ_SESSION_STATUS_TO_TARGET_STATUS[quiz_session_status]
