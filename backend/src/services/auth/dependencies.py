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

import uuid

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from src.api.errors import AuthenticationError, ForbiddenError
from src.db import get_db
from src.models.demo_instructor_profile import DemoInstructorProfile
from src.models.learner_profile import LearnerProfile
from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.tokens import SESSION_COOKIE_NAME, SessionClaims, verify_token

# Every route that depends on `current_instructor` only ever reads
# `.instructor_id` off the result (never `.email`/`.password_hash`), so
# a real and a demo instructor are interchangeable at the type's actual
# usage sites -- see tokens.py's `AccountType` docstring for why the
# two are still distinct session-claim types rather than one.
InstructorAccount = RealInstructorAccount | DemoInstructorProfile


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


def optional_session_claims(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> SessionClaims | None:
    """`None` (never raises) when there's no cookie or it doesn't verify --
    for routes that are unauthenticated by default (spec 005's quiz
    endpoints) but need to conditionally check a guardian's identity only
    when the resource in question turns out to require it (spec 011
    research.md §2's assignment-linked-session check). Unlike
    `current_session_claims`, absence of a session is not itself an
    error here -- the caller decides whether that's a problem."""
    if session_cookie is None:
        return None
    return verify_token(session_cookie)


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


def require_learner_ownership_if_real(
    db: Session, *, learner_id: uuid.UUID, claims: SessionClaims | None
) -> LearnerProfile | None:
    """Closes the learner_id-enumeration gap on learner-scoped routes
    (`mastery.py`, `mastery_history.py`, `recommendation.py`,
    `sequencing_preview.py`, `questions.py`'s `next-question`): a real,
    non-demo learner's data requires a guardian session that owns it.
    Originally read-only (GET) call sites only; `mastery.py`'s
    `career-connections-preference` `PATCH` (spec 039) is the first write
    reusing this same gate -- the no-op-for-demo behavior below applies
    to that write exactly as it already does to every read, which is a
    known, deliberate tradeoff for the demo learner specifically (see
    that route's own docstring), not an oversight here.

    Deliberately a no-op for a nonexistent or demo `learner_id` -- each
    of those routes already has its own tested contract for "this id
    doesn't identify a real, someone-else's learner" (e.g. `mastery.py`
    degrading to an empty response for a deleted learner vs.
    `recommendation.py`'s 404), which this must not disturb. Unlike
    `tutor.py`'s `_authorize_learner`, this does not collapse a
    nonexistent id into the same 403 -- these routes' existing
    not-found/degrade behavior for that case predates this check and is
    covered by other tests.

    Returns the fetched `LearnerProfile` (or `None`, if it doesn't
    exist) so callers that need it next -- e.g. `recommendation.py`'s
    own not-found check -- can reuse this lookup instead of repeating
    it."""
    learner = db.get(LearnerProfile, learner_id)
    if learner is None or learner.is_demo:
        return learner
    if (
        claims is None
        or claims.account_type != "guardian"
        or learner.guardian_id != claims.account_id
    ):
        raise ForbiddenError("not_your_learner")
    return learner


def current_instructor(
    claims: SessionClaims = Depends(current_session_claims),
    db: Session = Depends(get_db),
) -> InstructorAccount:
    if claims.account_type == "instructor":
        instructor = db.get(RealInstructorAccount, claims.account_id)
        if instructor is None:
            raise AuthenticationError("instructor_account_not_found")
        return instructor
    if claims.account_type == "demo_instructor":
        demo_instructor = db.get(DemoInstructorProfile, claims.account_id)
        if demo_instructor is None:
            raise AuthenticationError("instructor_account_not_found")
        return demo_instructor
    raise AuthenticationError("instructor_session_required")
