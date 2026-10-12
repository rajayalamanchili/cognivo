"""Unit tests: `backend/src/services/auth/reset_tokens.py` (spec 045
research.md §2/§3).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import datetime
import uuid

from sqlalchemy.exc import IntegrityError

from src.models.enums import AuthorizedByType
from src.models.password_reset_token import PasswordResetToken
from src.models.real_guardian_account import RealGuardianAccount
from src.services.auth import reset_tokens


def _make_guardian(db_session) -> RealGuardianAccount:
    guardian = RealGuardianAccount(
        email=f"guardian-{uuid.uuid4()}@example.com", password_hash="x", is_demo=False
    )
    db_session.add(guardian)
    db_session.commit()
    db_session.refresh(guardian)
    return guardian


def test_issue_sets_hash_and_one_hour_expiry(db_session):
    guardian = _make_guardian(db_session)
    raw_token = reset_tokens.issue(db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id)

    row = db_session.query(PasswordResetToken).one()
    assert row.token_hash != raw_token
    assert row.used_at is None
    # `expires_at` is computed from Python's clock, `created_at` from
    # the DB server's (`server_default=func.now()`) -- compare against
    # Python's own clock instead of the DB row's `created_at` to avoid
    # asserting the two clocks agree to the second.
    now = datetime.datetime.now(datetime.UTC)
    assert (
        now + datetime.timedelta(minutes=59)
        < row.expires_at
        < now + datetime.timedelta(hours=1, minutes=1)
    )


def test_find_by_raw_token_round_trip(db_session):
    guardian = _make_guardian(db_session)
    raw_token = reset_tokens.issue(db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id)

    found = reset_tokens.find_by_raw_token(db_session, raw_token)
    assert found is not None
    assert found.account_id == guardian.guardian_id

    assert reset_tokens.find_by_raw_token(db_session, "not-a-real-token") is None


def test_issuing_a_new_token_invalidates_the_prior_one(db_session):
    guardian = _make_guardian(db_session)
    first_token = reset_tokens.issue(db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id)
    second_token = reset_tokens.issue(db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id)

    first_row = reset_tokens.find_by_raw_token(db_session, first_token)
    second_row = reset_tokens.find_by_raw_token(db_session, second_token)
    assert first_row.used_at is not None
    assert second_row.used_at is None


def test_expired_token_is_found_but_distinguishable_from_invalid(db_session):
    guardian = _make_guardian(db_session)
    raw_token = reset_tokens.issue(db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id)
    row = reset_tokens.find_by_raw_token(db_session, raw_token)
    row.expires_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=1)
    db_session.commit()

    found = reset_tokens.find_by_raw_token(db_session, raw_token)
    assert found is not None
    assert found.expires_at <= datetime.datetime.now(datetime.UTC)


def test_recently_requested_true_within_window_false_after(db_session):
    guardian = _make_guardian(db_session)
    reset_tokens.issue(db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id)

    assert reset_tokens.recently_requested(
        db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id
    )

    row = db_session.query(PasswordResetToken).one()
    row.created_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=61)
    db_session.commit()

    assert not reset_tokens.recently_requested(
        db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id
    )


def test_concurrent_issue_retries_once_on_partial_unique_index_violation(db_session, monkeypatch):
    """Simulates two requests racing past the invalidate-then-insert
    step: the first `db.commit()` raises `IntegrityError` (another
    session already inserted a still-valid row for this account between
    this session's UPDATE and INSERT), and `issue` retries once rather
    than propagating it."""
    guardian = _make_guardian(db_session)

    calls = {"n": 0}
    real_commit = db_session.commit

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("duplicate", {}, Exception("duplicate"))
        return real_commit()

    monkeypatch.setattr(db_session, "commit", flaky_commit)

    raw_token = reset_tokens.issue(db_session, AuthorizedByType.GUARDIAN, guardian.guardian_id)
    assert raw_token
    assert calls["n"] == 2
