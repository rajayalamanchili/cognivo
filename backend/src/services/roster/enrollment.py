"""Roster creation/update and enrollment-gating logic (FR-004-FR-007a).

An `open` roster's join is immediate; a `closed` roster's join creates
(or returns an existing) pending `EnrollmentRequest`, decided later by
the owning instructor via `approve_request`/`decline_request`. Both
join paths are idempotent against an already-active `Enrollment` for
the same (`learner_id`, `roster_id`) pair -- `uq_enrollments_learner_roster`
is the actual invariant; these checks exist so a repeat click returns
the existing outcome instead of racing that constraint into an
`IntegrityError`.
"""

import datetime
import secrets
import string
import uuid

from sqlalchemy.orm import Session

from src.api.errors import ConflictError, NotFoundError, UnprocessableError
from src.models.classroom_roster import ClassroomRoster
from src.models.enrollment import Enrollment
from src.models.enrollment_request import EnrollmentRequest
from src.models.enums import AuthorizedByType, EnrollmentDecision, EnrollmentMode
from src.models.grade_band import GradeBand

_JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits
_JOIN_CODE_SUFFIX_LENGTH = 4
_MAX_JOIN_CODE_ATTEMPTS = 5


def _generate_join_code(db: Session, subject_id: str) -> str:
    prefix = "".join(ch for ch in subject_id.upper() if ch.isalnum())[:3] or "SUB"
    for _ in range(_MAX_JOIN_CODE_ATTEMPTS):
        suffix = "".join(
            secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(_JOIN_CODE_SUFFIX_LENGTH)
        )
        candidate = f"{prefix}-{suffix}"
        collision = db.query(ClassroomRoster).filter(ClassroomRoster.join_code == candidate).first()
        if collision is None:
            return candidate
    # 36**4 codes per prefix -- a collision on every one of
    # _MAX_JOIN_CODE_ATTEMPTS tries is astronomically unlikely; fail
    # loudly rather than ever return (and let the caller insert) a
    # colliding code.
    raise RuntimeError(f"could not generate a unique join code for subject {subject_id!r}")


def _check_grade_matches_subject(db: Session, subject_id: str, grade: int) -> None:
    """spec 040 FR-009: a roster's declared `grade` must overlap its
    subject's own `grade_bands` -- an ungraded subject (e.g. `biology`,
    zero `GradeBand` rows) imposes no restriction at all, the same
    opt-in-per-subject precedent `grade_bands` itself already follows."""
    subject_grades = {
        row.grade for row in db.query(GradeBand).filter(GradeBand.subject_id == subject_id)
    }
    if subject_grades and grade not in subject_grades:
        raise UnprocessableError(
            f"roster grade {grade} does not overlap subject {subject_id!r}'s "
            f"declared grade_bands {sorted(subject_grades)}"
        )


def create_roster(
    db: Session,
    *,
    instructor_id: uuid.UUID,
    subject_id: str,
    enrollment_mode: EnrollmentMode,
    grade: int | None = None,
) -> ClassroomRoster:
    """A `join_code` is generated for every roster regardless of mode --
    `POST /api/rosters/join`'s request body carries only `learner_id`
    and `join_code` (no `roster_id`), so it's the only mechanism that
    identifies which roster a join attempt targets, closed included.
    The API layer (`api/routes/rosters.py`'s `_roster_out`) is what
    keeps a closed roster's code out of the create/PATCH response
    (contracts/api.md: "`join_code` is `null` in the response when
    `enrollment_mode: closed`") -- the column itself is never null.

    `grade` (spec 040 FR-009) is optional; when given, it's validated
    against the subject's own `GradeBand` rows before anything is
    written -- a mismatch never creates a roster."""
    if grade is not None:
        _check_grade_matches_subject(db, subject_id, grade)
    roster = ClassroomRoster(
        instructor_id=instructor_id,
        subject_id=subject_id,
        enrollment_mode=enrollment_mode,
        grade=grade,
        join_code=_generate_join_code(db, subject_id),
    )
    db.add(roster)
    db.commit()
    db.refresh(roster)
    return roster


def _apply_roster_enrollment_mode(roster: ClassroomRoster, enrollment_mode: EnrollmentMode) -> None:
    roster.enrollment_mode = enrollment_mode
    # spec 041 FR-018: closing a roster implicitly stops listing it,
    # rather than erroring -- the instructor is closing it anyway, and
    # "closed AND listed" must never coexist (data-model.md's mutual
    # exclusion rule).
    if enrollment_mode == EnrollmentMode.CLOSED:
        roster.is_listed = False


def _apply_roster_is_listed(
    roster: ClassroomRoster, *, is_listed: bool, instructor_display_name: str | None
) -> None:
    """spec 041 FR-017/FR-018: the single enforcement point for both
    mutual-exclusion rules, applied identically whether the owning
    instructor account is brand-new or pre-existing -- no special-casing
    between the two (data-model.md's Validation rules)."""
    if is_listed:
        if roster.enrollment_mode == EnrollmentMode.CLOSED:
            raise UnprocessableError("cannot_list_closed_roster")
        if not instructor_display_name:
            raise UnprocessableError("instructor_display_name_required")
    roster.is_listed = is_listed


def update_roster(
    db: Session,
    *,
    roster: ClassroomRoster,
    enrollment_mode: EnrollmentMode,
    is_listed: bool | None,
    instructor_display_name: str | None,
) -> ClassroomRoster:
    """`PATCH /api/rosters/{roster_id}`'s single entry point for both
    fields together (Claude Code Review finding on PR #109): applies
    both mutations in memory and validates `is_listed` against the
    *already-applied* `enrollment_mode` change before committing either.
    Previously two separately-committing functions -- a request ending
    in a 422 (e.g. closing a roster while also trying to list it) could
    still persist the enrollment_mode change, since that commit had
    already happened before the is_listed validation ran."""
    _apply_roster_enrollment_mode(roster, enrollment_mode)
    if is_listed is not None:
        _apply_roster_is_listed(
            roster, is_listed=is_listed, instructor_display_name=instructor_display_name
        )
    db.commit()
    db.refresh(roster)
    return roster


def _existing_enrollment(
    db: Session, *, learner_id: uuid.UUID, roster_id: uuid.UUID
) -> Enrollment | None:
    return (
        db.query(Enrollment)
        .filter(Enrollment.learner_id == learner_id, Enrollment.roster_id == roster_id)
        .first()
    )


def join_roster(
    db: Session, *, learner_id: uuid.UUID, guardian_id: uuid.UUID, join_code: str
) -> tuple[str, Enrollment | EnrollmentRequest]:
    """Returns `("enrolled", Enrollment)` or `("pending", EnrollmentRequest)`."""
    roster = db.query(ClassroomRoster).filter(ClassroomRoster.join_code == join_code).first()
    if roster is None:
        raise NotFoundError("invalid_join_code")

    existing_enrollment = _existing_enrollment(
        db, learner_id=learner_id, roster_id=roster.roster_id
    )
    if existing_enrollment is not None:
        return ("enrolled", existing_enrollment)

    if roster.enrollment_mode == EnrollmentMode.OPEN:
        enrollment = Enrollment(
            learner_id=learner_id,
            roster_id=roster.roster_id,
            authorized_by_type=AuthorizedByType.GUARDIAN,
            authorized_by_id=guardian_id,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return ("enrolled", enrollment)

    # closed: return the existing pending request rather than duplicate it
    # (Edge Cases).
    existing_request = (
        db.query(EnrollmentRequest)
        .filter(
            EnrollmentRequest.learner_id == learner_id,
            EnrollmentRequest.roster_id == roster.roster_id,
            EnrollmentRequest.decision.is_(None),
        )
        .first()
    )
    if existing_request is not None:
        return ("pending", existing_request)

    request = EnrollmentRequest(learner_id=learner_id, roster_id=roster.roster_id)
    db.add(request)
    db.commit()
    db.refresh(request)
    return ("pending", request)


def approve_request(
    db: Session, *, request: EnrollmentRequest, instructor_id: uuid.UUID
) -> Enrollment:
    if request.decision is not None:
        raise ConflictError("request_already_decided")

    existing_enrollment = _existing_enrollment(
        db, learner_id=request.learner_id, roster_id=request.roster_id
    )
    request.decision = EnrollmentDecision.APPROVED
    request.decided_at = datetime.datetime.now(datetime.UTC)

    if existing_enrollment is not None:
        db.commit()
        db.refresh(existing_enrollment)
        return existing_enrollment

    enrollment = Enrollment(
        learner_id=request.learner_id,
        roster_id=request.roster_id,
        authorized_by_type=AuthorizedByType.INSTRUCTOR,
        authorized_by_id=instructor_id,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment


def decline_request(db: Session, *, request: EnrollmentRequest) -> None:
    if request.decision is not None:
        raise ConflictError("request_already_decided")
    request.decision = EnrollmentDecision.DECLINED
    request.decided_at = datetime.datetime.now(datetime.UTC)
    db.commit()


def unenroll(db: Session, *, roster_id: uuid.UUID, learner_id: uuid.UUID) -> None:
    """Deletes only the `Enrollment` row (FR-007a) -- never the
    learner's account or any other data."""
    db.query(Enrollment).filter(
        Enrollment.roster_id == roster_id, Enrollment.learner_id == learner_id
    ).delete()
    db.commit()
