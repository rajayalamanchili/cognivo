"""JWT session tokens (research.md §1, tech-stack.md's Authentication
section) -- stateless: verification is a pure function of the token's
signature and claims, no server-side session store (Constitution
Principle IX).

`SESSION_COOKIE_NAME` is defined here (not in the route layer) so every
route that sets the cookie (`api/routes/auth.py`, `api/routes/
demo_instructor.py`) and the dependency that reads it (`services/auth/
dependencies.py`) can't drift apart -- `set_session_cookie` below is the
one place the cookie's actual attributes (httpOnly/Secure/SameSite) are
set, for the same reason.
"""

import datetime
import os
import uuid
from dataclasses import dataclass
from typing import Literal

import jwt
from fastapi import Response

SESSION_COOKIE_NAME = "cognivo_session"
_ALGORITHM = "HS256"
_TOKEN_TTL = datetime.timedelta(days=30)
_COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

# "demo_instructor" is a third, distinct account type from "instructor"
# (research.md/`/speckit-clarify`, spec 010 Phase 7): `GET
# /api/demo-instructor` issues a session the same way login does, but
# naming it "instructor" would make `current_instructor`'s
# `RealInstructorAccount` lookup ambiguous with a `DemoInstructorProfile`
# id from a completely different table -- keeping the claim distinct
# lets `current_instructor` route to the right table deliberately
# rather than by ID-collision luck.
AccountType = Literal["guardian", "instructor", "demo_instructor"]

_VALID_ACCOUNT_TYPES = ("guardian", "instructor", "demo_instructor")


@dataclass(frozen=True)
class SessionClaims:
    account_type: AccountType
    account_id: uuid.UUID


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def issue_token(*, account_type: AccountType, account_id: uuid.UUID) -> str:
    now = datetime.datetime.now(datetime.UTC)
    claims = {
        "account_type": account_type,
        "account_id": str(account_id),
        "iat": now,
        "exp": now + _TOKEN_TTL,
    }
    return jwt.encode(claims, _secret(), algorithm=_ALGORITHM)


def verify_token(token: str) -> SessionClaims | None:
    """`None` on any invalid/expired/malformed token -- callers (the
    `current_guardian`/`current_instructor` FastAPI dependencies) turn
    that into a 401, never an unhandled exception."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    except jwt.InvalidTokenError:
        return None

    account_type = payload.get("account_type")
    account_id = payload.get("account_id")
    if account_type not in _VALID_ACCOUNT_TYPES or not isinstance(account_id, str):
        return None
    try:
        return SessionClaims(account_type=account_type, account_id=uuid.UUID(account_id))
    except ValueError:
        return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
