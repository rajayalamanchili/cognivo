"""FastAPI `Depends()` functions resolving "who is making this request"
from the session cookie (research.md §1) -- the sole authentication gate
every guardian-/instructor-only route sits behind. No server-side
session store: each call is a pure function of the cookie's JWT
signature/claims plus one lookup of the account it names.
"""

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.tokens import SESSION_COOKIE_NAME, SessionClaims, verify_token


def _current_claims(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> SessionClaims:
    if session_cookie is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    claims = verify_token(session_cookie)
    if claims is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return claims


def current_guardian(
    claims: SessionClaims = Depends(_current_claims),
    db: Session = Depends(get_db),
) -> RealGuardianAccount:
    if claims.account_type != "guardian":
        raise HTTPException(status_code=401, detail="guardian session required")
    guardian = db.get(RealGuardianAccount, claims.account_id)
    if guardian is None:
        raise HTTPException(status_code=401, detail="guardian account not found")
    return guardian


def current_instructor(
    claims: SessionClaims = Depends(_current_claims),
    db: Session = Depends(get_db),
) -> RealInstructorAccount:
    if claims.account_type != "instructor":
        raise HTTPException(status_code=401, detail="instructor session required")
    instructor = db.get(RealInstructorAccount, claims.account_id)
    if instructor is None:
        raise HTTPException(status_code=401, detail="instructor account not found")
    return instructor
