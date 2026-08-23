"""FastAPI `Depends()` functions resolving "who is making this request"
from the session cookie (research.md §1) -- the sole authentication gate
every guardian-/instructor-only route sits behind. No server-side
session store: each call is a pure function of the cookie's JWT
signature/claims plus one lookup of the account it names.

Raises `AuthenticationError` (not a bare `HTTPException`), matching this
codebase's convention (`api/errors.py`) of routes/dependencies raising a
domain error and letting `main.py`'s exception handlers own the actual
status-code mapping.
"""

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from src.api.errors import AuthenticationError
from src.db import get_db
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.tokens import SESSION_COOKIE_NAME, SessionClaims, verify_token


def current_session_claims(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> SessionClaims:
    """Public (unlike the account-type-specific dependencies below) for
    routes that accept either a guardian or an instructor session and
    do their own type-specific authorization -- e.g. `DELETE
    /api/rosters/{roster_id}/enrollments/{learner_id}` (contracts/api.md:
    the owning instructor OR the enrolled learner's own guardian)."""
    if session_cookie is None:
        raise AuthenticationError("not_authenticated")
    claims = verify_token(session_cookie)
    if claims is None:
        raise AuthenticationError("invalid_session")
    return claims


def current_guardian(
    claims: SessionClaims = Depends(current_session_claims),
    db: Session = Depends(get_db),
) -> RealGuardianAccount:
    if claims.account_type != "guardian":
        raise AuthenticationError("guardian_session_required")
    guardian = db.get(RealGuardianAccount, claims.account_id)
    if guardian is None:
        raise AuthenticationError("guardian_account_not_found")
    return guardian


def current_instructor(
    claims: SessionClaims = Depends(current_session_claims),
    db: Session = Depends(get_db),
) -> RealInstructorAccount:
    if claims.account_type != "instructor":
        raise AuthenticationError("instructor_session_required")
    instructor = db.get(RealInstructorAccount, claims.account_id)
    if instructor is None:
        raise AuthenticationError("instructor_account_not_found")
    return instructor
