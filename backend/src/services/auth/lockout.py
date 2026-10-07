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
"""

import datetime

from src.models.real_guardian_account import RealGuardianAccount

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION_MINUTES = 15


def is_locked_out(guardian: RealGuardianAccount) -> bool:
    return (
        guardian.locked_until is not None
        and guardian.locked_until > datetime.datetime.now(datetime.UTC)
    )


def seconds_until_unlocked(guardian: RealGuardianAccount) -> int:
    assert guardian.locked_until is not None
    remaining = guardian.locked_until - datetime.datetime.now(datetime.UTC)
    return max(1, int(remaining.total_seconds()))


def record_failed_attempt(guardian: RealGuardianAccount) -> None:
    guardian.failed_login_attempts += 1
    if guardian.failed_login_attempts >= LOCKOUT_THRESHOLD:
        guardian.locked_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            minutes=LOCKOUT_DURATION_MINUTES
        )


def record_successful_attempt(guardian: RealGuardianAccount) -> None:
    guardian.failed_login_attempts = 0
    guardian.locked_until = None
