"""Integration test: `scripts/seed_default_instructor.py` (spec 043
FR-019/FR-020, research.md §5).

Requires a reachable `DATABASE_URL` -- see tests/conftest.py. Skips
otherwise.
"""

import pytest

from scripts.seed_default_instructor import seed_default_instructor
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.passwords import hash_password

pytestmark = pytest.mark.usefixtures("database_available")


def test_rejects_an_unset_email_or_password(db_session, monkeypatch):
    monkeypatch.delenv("DEFAULT_INSTRUCTOR_EMAIL", raising=False)
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_PASSWORD", "correct horse")
    with pytest.raises(SystemExit):
        seed_default_instructor()


def test_rejects_an_empty_string_email_or_password(db_session, monkeypatch):
    """Claude Code Review finding on PR #111: `.env.example` ships both
    as empty strings, not unset -- a copied-but-unfilled-in example must
    not silently create a broken account."""
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", "")
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_PASSWORD", "")
    with pytest.raises(SystemExit):
        seed_default_instructor()


def test_rejects_a_too_short_password(db_session, monkeypatch):
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", "seed-script-short-pw@example.com")
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_PASSWORD", "short")
    with pytest.raises(SystemExit):
        seed_default_instructor()


def test_refuses_to_adopt_an_existing_demo_flagged_row(db_session, monkeypatch):
    email = "seed-script-demo-flagged@example.com"
    demo_row = RealInstructorAccount(
        email=email, password_hash=hash_password("correct horse"), is_demo=True
    )
    db_session.add(demo_row)
    db_session.commit()

    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", email)
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_PASSWORD", "another password")
    with pytest.raises(SystemExit):
        seed_default_instructor()


def test_creates_a_real_non_demo_account_when_none_exists(db_session, monkeypatch):
    email = "seed-script-fresh@example.com"
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", email)
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_PASSWORD", "correct horse battery")

    instructor = seed_default_instructor()

    assert instructor.email == email
    assert instructor.is_demo is False


def test_reuses_an_existing_non_demo_row_without_rehashing(db_session, monkeypatch):
    email = "seed-script-existing@example.com"
    existing = RealInstructorAccount(
        email=email, password_hash=hash_password("original password"), is_demo=False
    )
    db_session.add(existing)
    db_session.commit()
    original_hash = existing.password_hash

    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", email)
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_PASSWORD", "a different password")

    instructor = seed_default_instructor()

    assert instructor.instructor_id == existing.instructor_id
    assert instructor.password_hash == original_hash
