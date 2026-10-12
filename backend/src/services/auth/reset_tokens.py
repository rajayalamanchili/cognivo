"""spec 045 research.md §2/§3: password-reset token issuance,
verification lookup, and the reset-request rate-limit check. The raw
token emailed to the user is never persisted -- only its SHA-256 hex
digest (research.md §2 explains why a fast hash, not Argon2, is the
right choice here, unlike `services/auth/passwords.py`)."""

import datetime
import hashlib
import secrets
import uuid

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.enums import AuthorizedByType
from src.models.password_reset_token import PasswordResetToken

RESET_TOKEN_TTL = datetime.timedelta(hours=1)
# research.md §3: no 429/counter -- a silent no-op within this window
# preserves FR-002's identical-response, no-account-enumeration
# guarantee while still bounding abuse.
RESET_REQUEST_MIN_INTERVAL = datetime.timedelta(seconds=60)


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def recently_requested(db: Session, account_type: AuthorizedByType, account_id: uuid.UUID) -> bool:
    """True if any token (used or not) for this account was created
    within the last `RESET_REQUEST_MIN_INTERVAL`."""
    cutoff = datetime.datetime.now(datetime.UTC) - RESET_REQUEST_MIN_INTERVAL
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.account_type == account_type,
            PasswordResetToken.account_id == account_id,
            PasswordResetToken.created_at > cutoff,
        )
        .first()
        is not None
    )


def issue(db: Session, account_type: AuthorizedByType, account_id: uuid.UUID) -> str:
    """Invalidates any still-valid prior token for this account, then
    inserts a new one, returning the raw (never-persisted) token to
    email (FR-004). One retry on the partial-unique-index `IntegrityError`
    -- a self-request racing itself across two tabs, not adversarial
    input, so a single retry is the right fix rather than a back-off
    loop (research.md §2)."""
    for attempt in range(2):
        db.query(PasswordResetToken).filter(
            PasswordResetToken.account_type == account_type,
            PasswordResetToken.account_id == account_id,
            PasswordResetToken.used_at.is_(None),
        ).update({PasswordResetToken.used_at: datetime.datetime.now(datetime.UTC)})

        raw_token = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                account_type=account_type,
                account_id=account_id,
                token_hash=_hash(raw_token),
                expires_at=datetime.datetime.now(datetime.UTC) + RESET_TOKEN_TTL,
            )
        )
        try:
            db.commit()
            return raw_token
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise
    raise AssertionError("unreachable")


def find_by_raw_token(db: Session, raw_token: str) -> PasswordResetToken | None:
    """A plain hash lookup, regardless of validity -- used only to
    classify an already-failed `claim()` as `reset_token_invalid` vs.
    `reset_token_expired` (contracts/api.md). Never the basis for a
    security decision on its own -- see `claim()` below."""
    return (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == _hash(raw_token))
        .first()
    )


def claim(db: Session, raw_token: str, account_type: AuthorizedByType) -> uuid.UUID | None:
    """Atomically marks a token used, returning its `account_id`, or
    `None` if the claim failed for any reason (no match, wrong role,
    already used, expired). This single conditional `UPDATE` is the
    sole arbiter of single-use (PR #115 review finding): a prior
    read-then-write (`find_by_raw_token` + a separate `used_at` set)
    let two concurrent reset-password requests for the same token both
    pass the read-time check and both succeed. Postgres's row lock on
    this `UPDATE` serializes any second concurrent claim attempt behind
    the first, and its `WHERE used_at IS NULL` re-evaluates against the
    now-committed row, so only one claim can ever match.

    Deliberately does not commit -- the caller folds this into the same
    transaction as the password change itself, so a failure setting the
    new password also rolls back the claim."""
    now = datetime.datetime.now(datetime.UTC)
    result = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == _hash(raw_token),
            PasswordResetToken.account_type == account_type,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.account_id)
    )
    row = result.first()
    return row[0] if row is not None else None
