"""Guardian/instructor register, login, and logout (contracts/api.md
"Auth" section, research.md §1-§2).

Sessions are a stateless JWT in an httpOnly cookie -- register and login
both set it the same way via `_set_session_cookie`; logout clears it.
Guardian and instructor accounts are two separate tables with
independently-unique email (research.md §2), so the same email may
register as both.
"""

import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.errors import AuthenticationError, ConflictError
from src.db import get_db
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.passwords import hash_password, verify_password
from src.services.auth.tokens import SESSION_COOKIE_NAME, issue_token

router = APIRouter()

# Matches tokens.py's own token TTL -- the cookie shouldn't outlive the
# JWT it carries.
_COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


class AuthCredentialsIn(BaseModel):
    """No `is_demo` field here at all (FR-016, SC-004) -- pydantic's
    default `extra="ignore"` behavior silently drops any client-supplied
    field this model doesn't declare, so a real sign-up can never honor
    a caller-supplied `is_demo: true`."""

    email: str
    password: str


class GuardianAuthOut(BaseModel):
    guardian_id: uuid.UUID


class InstructorAuthOut(BaseModel):
    instructor_id: uuid.UUID


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/api/auth/instructor/register", response_model=InstructorAuthOut, status_code=201)
def register_instructor(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> InstructorAuthOut:
    existing = (
        db.query(RealInstructorAccount).filter(RealInstructorAccount.email == body.email).first()
    )
    if existing is not None:
        raise ConflictError("email_taken")

    instructor = RealInstructorAccount(
        email=body.email, password_hash=hash_password(body.password), is_demo=False
    )
    db.add(instructor)
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
    _set_session_cookie(response, token)
    return InstructorAuthOut(instructor_id=instructor.instructor_id)


@router.post("/api/auth/instructor/login", response_model=InstructorAuthOut)
def login_instructor(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> InstructorAuthOut:
    instructor = (
        db.query(RealInstructorAccount).filter(RealInstructorAccount.email == body.email).first()
    )
    if instructor is None or not verify_password(body.password, instructor.password_hash):
        raise AuthenticationError("invalid_credentials")

    token = issue_token(account_type="instructor", account_id=instructor.instructor_id)
    _set_session_cookie(response, token)
    return InstructorAuthOut(instructor_id=instructor.instructor_id)


@router.post("/api/auth/guardian/register", response_model=GuardianAuthOut, status_code=201)
def register_guardian(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> GuardianAuthOut:
    existing = db.query(RealGuardianAccount).filter(RealGuardianAccount.email == body.email).first()
    if existing is not None:
        raise ConflictError("email_taken")

    guardian = RealGuardianAccount(
        email=body.email, password_hash=hash_password(body.password), is_demo=False
    )
    db.add(guardian)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("email_taken") from exc
    db.refresh(guardian)

    token = issue_token(account_type="guardian", account_id=guardian.guardian_id)
    _set_session_cookie(response, token)
    return GuardianAuthOut(guardian_id=guardian.guardian_id)


@router.post("/api/auth/guardian/login", response_model=GuardianAuthOut)
def login_guardian(
    body: AuthCredentialsIn, response: Response, db: Session = Depends(get_db)
) -> GuardianAuthOut:
    guardian = db.query(RealGuardianAccount).filter(RealGuardianAccount.email == body.email).first()
    if guardian is None or not verify_password(body.password, guardian.password_hash):
        raise AuthenticationError("invalid_credentials")

    token = issue_token(account_type="guardian", account_id=guardian.guardian_id)
    _set_session_cookie(response, token)
    return GuardianAuthOut(guardian_id=guardian.guardian_id)


@router.post("/api/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
