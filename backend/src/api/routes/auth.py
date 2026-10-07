"""Guardian/instructor register, login, and logout (contracts/api.md
"Auth" section, research.md §1-§2).

Sessions are a stateless JWT in an httpOnly cookie -- register and login
both set it the same way via `tokens.set_session_cookie`; logout clears
it. Guardian and instructor accounts are two separate tables with
independently-unique email (research.md §2), so the same email may
register as both.
"""

import datetime
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.errors import AuthenticationError, ConflictError, UnprocessableError
from src.db import get_db
from src.models.demo_instructor_profile import DemoInstructorProfile
from src.models.enums import AuthorizedByType, RetentionAccountType, RetentionEnrollmentStatus
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.models.retention_record import RetentionRecord
from src.services.auth.dependencies import (
    InstructorAccount,
    current_guardian,
    current_instructor,
    optional_session_claims,
)
from src.services.auth.passwords import hash_password, verify_password
from src.services.auth.tokens import (
    SESSION_COOKIE_NAME,
    AccountType,
    SessionClaims,
    issue_token,
    set_session_cookie,
)
from src.services.deletion.inactivity import INACTIVITY_RETENTION_PERIOD

router = APIRouter()

# A fixed-cost Argon2id verification run on the "no such account" login
# path too (PR #28 review) -- without this, verify_password only runs
# when an account exists, so response latency alone distinguishes
# "unknown email" from "wrong password," defeating the no-account-
# enumeration goal AuthenticationError's own docstring states. Computed
# once at import time, not per-request.
_DUMMY_PASSWORD_HASH = hash_password(uuid.uuid4().hex)


def _normalize_email(email: str) -> str:
    """Case-insensitive per research.md §2's uniqueness intent (PR #28
    review) -- unlike Postgres's default `=`, a person shouldn't get a
    different account (or fail to log back into the same one) purely
    because they capitalized their email differently this time."""
    return email.strip().lower()


class AuthCredentialsIn(BaseModel):
    """No `is_demo` field here at all (FR-016, SC-004) -- pydantic's
    default `extra="ignore"` behavior silently drops any client-supplied
    field this model doesn't declare, so a real sign-up can never honor
    a caller-supplied `is_demo: true`. `password`'s `min_length=8`
    matches the frontend's own enforced minimum (PR #28 review) --
    without a server-side copy of that constraint, it's trivially
    bypassed by calling this endpoint directly."""

    email: str
    password: str = Field(min_length=8)


class GuardianAuthOut(BaseModel):
    guardian_id: uuid.UUID


class InstructorAuthOut(BaseModel):
    instructor_id: uuid.UUID


@router.post("/api/auth/instructor/register", response_model=InstructorAuthOut, status_code=201)
def register_instructor(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> InstructorAuthOut:
    email = _normalize_email(body.email)
    existing = db.query(RealInstructorAccount).filter(RealInstructorAccount.email == email).first()
    if existing is not None:
        raise ConflictError("email_taken")

    instructor_id = uuid.uuid4()
    instructor = RealInstructorAccount(
        instructor_id=instructor_id,
        email=email,
        password_hash=hash_password(body.password),
        is_demo=False,
    )
    db.add(instructor)
    # RetentionAccountType.INSTRUCTOR exists specifically to drive
    # FR-010's 1-year post-inactivity clock for real instructor
    # accounts (PR #28 review) -- self-authorized, since an instructor
    # registers their own account rather than being added by someone
    # else the way a guardian adds a learner.
    db.add(
        RetentionRecord(
            account_type=RetentionAccountType.INSTRUCTOR,
            account_id=instructor_id,
            authorized_by_type=AuthorizedByType.INSTRUCTOR,
            authorized_by_id=instructor_id,
            enrollment_status=RetentionEnrollmentStatus.ACTIVE,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        # The SELECT above is check-then-act -- this UNIQUE constraint
        # (uq_real_instructor_accounts_email) is the actual arbiter for
        # a concurrent duplicate registration racing past it.
        db.rollback()
        raise ConflictError("email_taken") from exc
    db.refresh(instructor)

    token = issue_token(account_type="instructor", account_id=instructor.instructor_id)
    set_session_cookie(response, token)
    return InstructorAuthOut(instructor_id=instructor.instructor_id)


@router.post("/api/auth/instructor/login", response_model=InstructorAuthOut)
def login_instructor(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> InstructorAuthOut:
    email = _normalize_email(body.email)
    instructor = (
        db.query(RealInstructorAccount).filter(RealInstructorAccount.email == email).first()
    )
    password_hash = instructor.password_hash if instructor is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, password_hash)
    if instructor is None or not password_ok:
        raise AuthenticationError("invalid_credentials")

    token = issue_token(account_type="instructor", account_id=instructor.instructor_id)
    set_session_cookie(response, token)
    return InstructorAuthOut(instructor_id=instructor.instructor_id)


@router.post("/api/auth/guardian/register", response_model=GuardianAuthOut, status_code=201)
def register_guardian(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> GuardianAuthOut:
    email = _normalize_email(body.email)
    existing = db.query(RealGuardianAccount).filter(RealGuardianAccount.email == email).first()
    if existing is not None:
        raise ConflictError("email_taken")

    guardian = RealGuardianAccount(
        email=email, password_hash=hash_password(body.password), is_demo=False
    )
    db.add(guardian)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("email_taken") from exc
    db.refresh(guardian)

    token = issue_token(account_type="guardian", account_id=guardian.guardian_id)
    set_session_cookie(response, token)
    return GuardianAuthOut(guardian_id=guardian.guardian_id)


@router.post("/api/auth/guardian/login", response_model=GuardianAuthOut)
def login_guardian(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> GuardianAuthOut:
    email = _normalize_email(body.email)
    guardian = db.query(RealGuardianAccount).filter(RealGuardianAccount.email == email).first()
    password_hash = guardian.password_hash if guardian is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, password_hash)
    if guardian is None or not password_ok:
        raise AuthenticationError("invalid_credentials")

    token = issue_token(account_type="guardian", account_id=guardian.guardian_id)
    set_session_cookie(response, token)
    return GuardianAuthOut(guardian_id=guardian.guardian_id)


@router.post("/api/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


class GuardianMeIn(BaseModel):
    """spec 041 FR-009/FR-011. All fields optional -- only ones the
    client actually sent (`exclude_unset`) are changed, so e.g. omitting
    `weekly_summary_enabled` never resets it to `False`."""

    name: str | None = None
    email: str | None = None
    read_aloud_default: bool | None = None
    larger_text: bool | None = None
    reduce_motion: bool | None = None
    theme: Literal["system", "light", "dark"] | None = None
    quiz_finished_email_enabled: bool | None = None
    weekly_summary_enabled: bool | None = None


class GuardianMeOut(BaseModel):
    name: str | None
    email: str
    read_aloud_default: bool
    larger_text: bool
    reduce_motion: bool
    theme: str
    quiz_finished_email_enabled: bool
    weekly_summary_enabled: bool


def _guardian_me_out(guardian: RealGuardianAccount) -> GuardianMeOut:
    return GuardianMeOut(
        name=guardian.name,
        email=guardian.email,
        read_aloud_default=guardian.read_aloud_default,
        larger_text=guardian.larger_text,
        reduce_motion=guardian.reduce_motion,
        theme=guardian.theme,
        quiz_finished_email_enabled=guardian.quiz_finished_email_enabled,
        weekly_summary_enabled=guardian.weekly_summary_enabled,
    )


# Every `GuardianMeIn` field but `name` backs a NOT NULL column
# (real_guardian_account.py). `exclude_unset=True` below only drops
# fields the client never sent -- an explicit `null` for one of these
# still reaches `_normalize_email`/`setattr`, raising an unhandled
# AttributeError (email) or a NOT NULL `IntegrityError` that the
# `except IntegrityError` handler then misreports as `email_taken`.
_GUARDIAN_ME_NON_NULLABLE_FIELDS = (
    "email",
    "read_aloud_default",
    "larger_text",
    "reduce_motion",
    "theme",
    "quiz_finished_email_enabled",
    "weekly_summary_enabled",
)


@router.patch("/api/auth/guardian/me", response_model=GuardianMeOut)
def update_guardian_me(
    body: GuardianMeIn,
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> GuardianMeOut:
    updates = body.model_dump(exclude_unset=True)
    for field in _GUARDIAN_ME_NON_NULLABLE_FIELDS:
        if updates.get(field, False) is None:
            raise UnprocessableError(f"{field}_required")
    if "email" in updates:
        email = _normalize_email(updates["email"])
        existing = (
            db.query(RealGuardianAccount)
            .filter(
                RealGuardianAccount.email == email,
                RealGuardianAccount.guardian_id != guardian.guardian_id,
            )
            .first()
        )
        if existing is not None:
            raise ConflictError("email_taken")
        updates["email"] = email

    for field, value in updates.items():
        setattr(guardian, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("email_taken") from exc
    db.refresh(guardian)
    return _guardian_me_out(guardian)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/api/auth/guardian/change-password", status_code=204)
def change_guardian_password(
    body: ChangePasswordIn,
    response: Response,
    guardian: RealGuardianAccount = Depends(current_guardian),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(body.current_password, guardian.password_hash):
        raise AuthenticationError("invalid_credentials")
    guardian.password_hash = hash_password(body.new_password)
    # FR-022/research.md §6: invalidates every session token issued
    # before this moment on its next use (dependencies.py's
    # `current_guardian`) -- including the very cookie that authenticated
    # *this* request. Reissuing a fresh cookie here (Claude Code Review
    # finding on PR #109) keeps the caller's own browser tab logged in;
    # without it, the next request from this same tab/session would be
    # rejected as stale, silently logging the guardian out right after a
    # successful change.
    guardian.password_changed_at = datetime.datetime.now(datetime.UTC)
    db.commit()
    token = issue_token(account_type="guardian", account_id=guardian.guardian_id)
    set_session_cookie(response, token)


class InstructorMeIn(BaseModel):
    """spec 041 FR-017. The only field this endpoint changes --
    email/password changes for instructors are out of scope for this
    feature (contracts/api-changes.md)."""

    display_name: str = Field(min_length=1)


class InstructorMeOut(BaseModel):
    display_name: str


@router.patch("/api/auth/instructor/me", response_model=InstructorMeOut)
def update_instructor_me(
    body: InstructorMeIn,
    instructor: InstructorAccount = Depends(current_instructor),
    db: Session = Depends(get_db),
) -> InstructorMeOut:
    display_name = body.display_name.strip()
    if display_name == "":
        raise UnprocessableError("display_name_required")
    instructor.display_name = display_name
    db.commit()
    return InstructorMeOut(display_name=display_name)


class PendingDeletionWarningOut(BaseModel):
    target_type: str
    target_id: uuid.UUID
    warned_at: datetime.datetime
    scheduled_deletion_date: datetime.date


class WhoAmIOut(BaseModel):
    account_type: AccountType | None
    identifier: str | None = None
    pending_deletion_warnings: list[PendingDeletionWarningOut] = Field(default_factory=list)
    # spec 041 FR-009/FR-011/FR-012: populated only when account_type ==
    # "guardian" (same pattern pending_deletion_warnings already
    # follows) -- None for every other account type. `guardian_id` is
    # Settings' "delete my account" action's own target_id -- nothing
    # else in a guardian session response exposes it.
    guardian_id: uuid.UUID | None = None
    name: str | None = None
    read_aloud_default: bool | None = None
    larger_text: bool | None = None
    reduce_motion: bool | None = None
    theme: str | None = None
    quiz_finished_email_enabled: bool | None = None
    weekly_summary_enabled: bool | None = None


_GUARDIAN_ONLY_FIELDS = (
    "guardian_id",
    "name",
    "read_aloud_default",
    "larger_text",
    "reduce_motion",
    "theme",
    "quiz_finished_email_enabled",
    "weekly_summary_enabled",
)


def _pending_deletion_warnings(
    claims: SessionClaims, db: Session
) -> list[PendingDeletionWarningOut]:
    """spec 020 FR-011/research.md R9: a guardian sees one entry per
    linked learner whose `RetentionRecord` has been warned; an
    instructor sees at most one entry, for their own account. A demo
    session never has a `RetentionRecord` to find (FR-007), so this
    naturally returns an empty list for one."""
    if claims.account_type == "guardian":
        rows = (
            db.query(LearnerProfile, RetentionRecord)
            .join(
                RetentionRecord,
                LearnerProfile.retention_record_id == RetentionRecord.retention_record_id,
            )
            .filter(
                LearnerProfile.guardian_id == claims.account_id,
                RetentionRecord.inactivity_warning_sent_at.isnot(None),
            )
            .all()
        )
        return [
            PendingDeletionWarningOut(
                target_type="learner",
                target_id=learner.learner_id,
                warned_at=record.inactivity_warning_sent_at,
                scheduled_deletion_date=(
                    record.became_inactive_at + INACTIVITY_RETENTION_PERIOD
                ).date(),
            )
            for learner, record in rows
        ]

    if claims.account_type == "instructor":
        record = (
            db.query(RetentionRecord)
            .filter(
                RetentionRecord.account_type == RetentionAccountType.INSTRUCTOR,
                RetentionRecord.account_id == claims.account_id,
                RetentionRecord.inactivity_warning_sent_at.isnot(None),
            )
            .first()
        )
        if record is None:
            return []
        return [
            PendingDeletionWarningOut(
                target_type="instructor",
                target_id=claims.account_id,
                warned_at=record.inactivity_warning_sent_at,
                scheduled_deletion_date=(
                    record.became_inactive_at + INACTIVITY_RETENTION_PERIOD
                ).date(),
            )
        ]

    return []


@router.get("/api/auth/whoami", response_model=WhoAmIOut)
def whoami(
    claims: SessionClaims | None = Depends(optional_session_claims),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Read-only session-identity check for the frontend nav (no
    business logic gated on this -- every real authorization decision
    still happens per-route via `current_guardian`/`current_instructor`,
    same as before this endpoint existed). `identifier` is the login
    email for a real guardian/instructor, or the seeded display name for
    a demo instructor -- `None` for a `None` `claims` or a session whose
    account row no longer exists.

    A plain dict via `JSONResponse`, not `WhoAmIOut(...)` (same reasoning
    `questions.py`'s `answer_question` already documents for its own
    response): the six new guardian-preference fields (FR-009/FR-011)
    must be *absent*, not merely `null`, for every non-guardian account
    type, to keep this endpoint's pre-existing response shape -- and the
    tests asserting it -- byte-for-byte unchanged for every other
    account type. A single `response_model_exclude_none` can't apply to
    some fields (these six) but not others (`account_type`/`identifier`,
    which must stay present as `null`), so this builds the body
    explicitly instead."""
    if claims is None:
        return JSONResponse(
            WhoAmIOut(account_type=None).model_dump(
                mode="json", exclude=set(_GUARDIAN_ONLY_FIELDS)
            )
        )

    identifier: str | None = None
    guardian_fields: dict[str, object] = {}
    if claims.account_type == "guardian":
        guardian = db.get(RealGuardianAccount, claims.account_id)
        identifier = guardian.email if guardian else None
        if guardian is not None:
            guardian_fields = {
                "guardian_id": guardian.guardian_id,
                "name": guardian.name,
                "read_aloud_default": guardian.read_aloud_default,
                "larger_text": guardian.larger_text,
                "reduce_motion": guardian.reduce_motion,
                "theme": guardian.theme,
                "quiz_finished_email_enabled": guardian.quiz_finished_email_enabled,
                "weekly_summary_enabled": guardian.weekly_summary_enabled,
            }
    elif claims.account_type == "instructor":
        instructor = db.get(RealInstructorAccount, claims.account_id)
        identifier = instructor.email if instructor else None
    elif claims.account_type == "demo_instructor":
        demo_instructor = db.get(DemoInstructorProfile, claims.account_id)
        identifier = demo_instructor.display_name if demo_instructor else None

    result = WhoAmIOut(
        account_type=claims.account_type,
        identifier=identifier,
        pending_deletion_warnings=_pending_deletion_warnings(claims, db),
        **guardian_fields,
    )
    exclude = set() if guardian_fields else set(_GUARDIAN_ONLY_FIELDS)
    return JSONResponse(result.model_dump(mode="json", exclude=exclude))
