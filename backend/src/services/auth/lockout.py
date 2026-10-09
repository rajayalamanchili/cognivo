"""Per-account login lockout (Claude Code Review finding on PR #109):
`/login` and `/change-password`'s `current_password` check both verify
a password with no throttle at all, so either is an unlimited brute-
force oracle -- `/login` needs no session, and `/change-password` could
be hammered by a stolen one. Stateless on Vercel (Principle IX -- no
in-memory counter survives between invocations), so the attempt count
lives on `RealGuardianAccount` itself rather than a separate table: the
same DB-backed-not-in-memory principle this codebase's other rate
limiters already use (`services/tutor/rate_limit.py`,
`services/grading_client/guardrails.py`), just keyed by account instead
of a trailing-window event-row count, since there's no existing
per-attempt event table for auth to count rows in.

Known, accepted trade-off (Code Review follow-up on PR #109): keying
solely on the account, with no IP component, means anyone who knows a
guardian's email can lock that guardian out of sign-in for
`LOCKOUT_DURATION_MINUTES` with `LOCKOUT_THRESHOLD` bad requests --
and since `/change-password` shares the same counter, a stolen session
can use it to lock out the legitimate owner. Adding an IP-keyed
component would need its own spec decision (a shared NAT/VPN exit
legitimately produces many guardians' traffic from one IP, so it's not
a drop-in change) rather than a reactive patch here.
"""

import datetime

from sqlalchemy import case, update
from sqlalchemy.orm import Session

from src.models.real_guardian_account import RealGuardianAccount
from src.models.real_instructor_account import RealInstructorAccount

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION_MINUTES = 15

# spec 043: both account types only ever get `failed_login_attempts`/
# `locked_until` read generically by the three functions below -- only
# `record_failed_attempt`'s UPDATE is coupled to a concrete model (its
# primary-key column name differs), so that one function isn't widened;
# see `record_failed_attempt_instructor` below instead.
AnyRealAccount = RealGuardianAccount | RealInstructorAccount


def is_locked_out(account: AnyRealAccount) -> bool:
    return (
        account.locked_until is not None
        and account.locked_until > datetime.datetime.now(datetime.UTC)
    )


def seconds_until_unlocked(account: AnyRealAccount) -> int:
    assert account.locked_until is not None
    remaining = account.locked_until - datetime.datetime.now(datetime.UTC)
    return max(1, int(remaining.total_seconds()))


def record_failed_attempt(db: Session, guardian: RealGuardianAccount) -> None:
    """A single `UPDATE ... SET failed_login_attempts = failed_login_attempts
    + 1` (Code Review finding on PR #109): the previous `guardian.
    failed_login_attempts += 1` read-modify-wrote the Python object's
    already-loaded value, so two concurrent guesses (normal on Vercel's
    per-request invocations) each computed `n + 1` from the same stale
    `n` and one increment was lost -- parallel guessing undercounted
    and could get more than `LOCKOUT_THRESHOLD` tries in. Doing the
    arithmetic in the `UPDATE` itself means Postgres reads the row's
    current value while it holds that row's lock, so the race is gone
    regardless of how many requests overlap.

    Also resets the counter here once `locked_until` has passed, in the
    same statement: without that, the count was still >= threshold from
    the expired lockout, so the very next failed attempt re-locked
    immediately instead of getting a fresh five tries.

    Leaves `guardian`'s in-memory attributes stale (the caller doesn't
    read them again before raising)."""
    now = datetime.datetime.now(datetime.UTC)
    lock_expired = (RealGuardianAccount.locked_until.isnot(None)) & (
        RealGuardianAccount.locked_until <= now
    )
    new_count = case((lock_expired, 1), else_=RealGuardianAccount.failed_login_attempts + 1)
    db.execute(
        update(RealGuardianAccount)
        .where(RealGuardianAccount.guardian_id == guardian.guardian_id)
        .values(
            failed_login_attempts=new_count,
            locked_until=case(
                (new_count >= LOCKOUT_THRESHOLD, now + datetime.timedelta(minutes=LOCKOUT_DURATION_MINUTES)),
                (lock_expired, None),
                else_=RealGuardianAccount.locked_until,
            ),
        )
    )


def record_failed_attempt_instructor(db: Session, instructor: RealInstructorAccount) -> None:
    """Identical in shape to `record_failed_attempt` above, targeting
    `RealInstructorAccount`/`instructor_id` instead -- kept as its own
    function rather than generalizing the `UPDATE` across two different
    primary-key column names (research.md §1)."""
    now = datetime.datetime.now(datetime.UTC)
    lock_expired = (RealInstructorAccount.locked_until.isnot(None)) & (
        RealInstructorAccount.locked_until <= now
    )
    new_count = case((lock_expired, 1), else_=RealInstructorAccount.failed_login_attempts + 1)
    db.execute(
        update(RealInstructorAccount)
        .where(RealInstructorAccount.instructor_id == instructor.instructor_id)
        .values(
            failed_login_attempts=new_count,
            locked_until=case(
                (new_count >= LOCKOUT_THRESHOLD, now + datetime.timedelta(minutes=LOCKOUT_DURATION_MINUTES)),
                (lock_expired, None),
                else_=RealInstructorAccount.locked_until,
            ),
        )
    )


def record_successful_attempt(account: AnyRealAccount) -> None:
    account.failed_login_attempts = 0
    account.locked_until = None
