"""Unit tests: `src/services/roster/default_instructor.py` (spec 043
research.md §5), T020.

Requires a reachable `DATABASE_URL` -- see tests/conftest.py.
"""

import pytest

from src.models.classroom_roster import ClassroomRoster
from src.models.real_instructor_account import RealInstructorAccount
from src.services.auth.passwords import hash_password
from src.services.roster.default_instructor import (
    ensure_default_instructor_roster_for_subject,
    get_default_instructor,
)

pytestmark = pytest.mark.usefixtures("database_available")

_EMAIL = "default-instructor-unit@example.com"


def _make_default_instructor(db_session) -> RealInstructorAccount:
    instructor = RealInstructorAccount(
        email=_EMAIL,
        password_hash=hash_password("correct horse"),
        is_demo=False,
        display_name="Cognivo",
    )
    db_session.add(instructor)
    db_session.commit()
    db_session.refresh(instructor)
    return instructor


def test_get_default_instructor_returns_none_when_env_var_unset(db_session, monkeypatch):
    monkeypatch.delenv("DEFAULT_INSTRUCTOR_EMAIL", raising=False)
    assert get_default_instructor(db_session) is None


def test_get_default_instructor_returns_none_when_no_matching_row(db_session, monkeypatch):
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", _EMAIL)
    assert get_default_instructor(db_session) is None


def test_get_default_instructor_returns_the_matching_row(db_session, monkeypatch):
    instructor = _make_default_instructor(db_session)
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", _EMAIL)
    found = get_default_instructor(db_session)
    assert found is not None
    assert found.instructor_id == instructor.instructor_id


def test_ensure_roster_is_a_no_op_when_no_default_instructor_exists(db_session, monkeypatch):
    monkeypatch.delenv("DEFAULT_INSTRUCTOR_EMAIL", raising=False)
    ensure_default_instructor_roster_for_subject(db_session, "algebra-1")
    assert db_session.query(ClassroomRoster).count() == 0


def test_ensure_roster_creates_exactly_one_open_listed_roster(
    db_session, monkeypatch, algebra_subject
):
    instructor = _make_default_instructor(db_session)
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", _EMAIL)

    ensure_default_instructor_roster_for_subject(db_session, algebra_subject.subject_id)

    rosters = (
        db_session.query(ClassroomRoster)
        .filter(ClassroomRoster.instructor_id == instructor.instructor_id)
        .all()
    )
    assert len(rosters) == 1
    assert rosters[0].subject_id == algebra_subject.subject_id
    assert rosters[0].enrollment_mode.value == "open"
    assert rosters[0].is_listed is True


def test_ensure_roster_is_idempotent_on_a_second_call(db_session, monkeypatch, algebra_subject):
    _make_default_instructor(db_session)
    monkeypatch.setenv("DEFAULT_INSTRUCTOR_EMAIL", _EMAIL)

    ensure_default_instructor_roster_for_subject(db_session, algebra_subject.subject_id)
    ensure_default_instructor_roster_for_subject(db_session, algebra_subject.subject_id)

    assert db_session.query(ClassroomRoster).count() == 1
