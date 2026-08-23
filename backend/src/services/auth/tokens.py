"""JWT session tokens (research.md §1, tech-stack.md's Authentication
section) -- stateless: verification is a pure function of the token's
signature and claims, no server-side session store (Constitution
Principle IX).

`SESSION_COOKIE_NAME` is defined here (not in the route layer) so the
route that sets the cookie (`api/routes/auth.py`) and the dependency
that reads it (`services/auth/dependencies.py`) can't drift apart.
"""

import datetime
import os
import uuid
from dataclasses import dataclass
from typing import Literal

import jwt

SESSION_COOKIE_NAME = "cognivo_session"
_ALGORITHM = "HS256"
_TOKEN_TTL = datetime.timedelta(days=30)

AccountType = Literal["guardian", "instructor"]


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
    if account_type not in ("guardian", "instructor") or not isinstance(account_id, str):
        return None
    try:
        return SessionClaims(account_type=account_type, account_id=uuid.UUID(account_id))
    except ValueError:
        return None
