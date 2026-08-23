"""Guardian/instructor register, login, and logout (contracts/api.md
"Auth" section, research.md §1-§2).

Sessions are a stateless JWT in an httpOnly cookie -- register and login
both set it the same way via `tokens.set_session_cookie`; logout clears
it. Guardian and instructor accounts are two separate tables with
independently-unique email (research.md §2), so the same email may
register as both.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.errors import AuthenticationError, ConflictError
from src.db import get_db
from src.models.enums import AuthorizedByType, RetentionAccountType, RetentionEnrollmentStatus
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.models.retention_record import RetentionRecord
from src.services.auth.passwords import hash_password, verify_password
from src.services.auth.tokens import SESSION_COOKIE_NAME, issue_token, set_session_cookie

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
