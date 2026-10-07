"""Unit tests: `src/services/auth/lockout.py`'s `record_failed_attempt` --
Code Review follow-up on PR #109: the previous `guardian.
failed_login_attempts += 1` was a non-atomic read-modify-write (lost
increments under concurrent requests) and never reset the counter once
`locked_until` had passed (so the first failure after a lockout expired
re-locked immediately instead of getting a fresh `LOCKOUT_THRESHOLD`
tries). `test_auth_guardian_settings.py` covers the route-level happy
path; these two cover exactly the bugs the review found, which no
single-request happy-path test can exercise.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime
import uuid

import pytest

from src.models.real_guardian_account import RealGuardianAccount
from src.services.auth.lockout import LOCKOUT_THRESHOLD, is_locked_out, record_failed_attempt

pytestmark = pytest.mark.usefixtures("database_available")


def _make_guardian(db_session) -> RealGuardianAccount:
    guardian = RealGuardianAccount(
        email=f"lockout-unit-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(guardian)
    db_session.commit()
    db_session.refresh(guardian)
    return guardian


def test_record_failed_attempt_is_atomic_under_concurrent_stale_reads(db_session):
    """Two requests, each holding its own stale in-memory copy of the
    same guardian row (as two concurrent FastAPI requests would) --
    both call `record_failed_attempt` without re-reading in between.
    A `+= 1` on the Python object would compute `0 + 1` twice and lose
    one increment; the atomic `UPDATE` must land both."""
    guardian = _make_guardian(db_session)
    guardian_copy = db_session.get(RealGuardianAccount, guardian.guardian_id)
    db_session.expunge(guardian_copy)

    record_failed_attempt(db_session, guardian)
    record_failed_attempt(db_session, guardian_copy)
    db_session.commit()

    db_session.expire_all()
    refreshed = db_session.get(RealGuardianAccount, guardian.guardian_id)
    assert refreshed.failed_login_attempts == 2


def test_record_failed_attempt_resets_counter_after_lockout_expires(db_session):
    """Lock the account out, then fast-forward `locked_until` into the
    past (simulating the 15-minute wait). The next failure must start a
    fresh count of 1, not re-lock immediately from the stale count."""
    guardian = _make_guardian(db_session)
    for _ in range(LOCKOUT_THRESHOLD):
        record_failed_attempt(db_session, guardian)
        db_session.commit()
        db_session.refresh(guardian)
    assert is_locked_out(guardian)

    guardian.locked_until = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1)
    db_session.commit()

    record_failed_attempt(db_session, guardian)
    db_session.commit()
    db_session.refresh(guardian)

    assert guardian.failed_login_attempts == 1
    assert not is_locked_out(guardian)
