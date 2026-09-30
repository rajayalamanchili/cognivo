"""Unit tests: `get_or_check_moderation()`'s exact-signature lookup,
instruction-version scoping, and fail-open behavior (spec 026 FR-001/
FR-003/FR-005/FR-006/FR-008, research.md §2/§3).

Mirrors `test_question_cache.py`'s shape -- a real Postgres `db_session`
(no mocking the DB itself), a fake `check_fn` standing in for the real
moderation model call.
"""

import pytest

from src.models.moderation_cache import ModerationCache
from src.services.moderation_cache.cache import get_or_check_moderation

pytestmark = pytest.mark.usefixtures("database_available")

INSTRUCTION_VERSION = "v1"


def _check_fn(*, result: bool = True, raises: bool = False):
    calls = {"count": 0}

    async def _fn():
        calls["count"] += 1
        if raises:
            raise RuntimeError("boom")
        return result

    _fn.calls = calls
    return _fn


async def test_no_matching_signature_is_a_miss_and_inserts_a_row(db_session):
    check_fn = _check_fn(result=True)

    allowed, outcome = await get_or_check_moderation(
        db_session, text="a brand new answer", instruction_version=INSTRUCTION_VERSION,
        check_fn=check_fn,
    )
    db_session.commit()

    assert outcome.hit is False
    assert check_fn.calls["count"] == 1
    assert allowed is True
    row = db_session.query(ModerationCache).one()
    assert row.allowed is True


async def test_matching_signature_and_version_is_a_hit_and_skips_check_fn(db_session):
    check_fn = _check_fn(result=False)
    await get_or_check_moderation(
        db_session, text="repeated text", instruction_version=INSTRUCTION_VERSION,
        check_fn=check_fn,
    )
    db_session.commit()

    allowed, outcome = await get_or_check_moderation(
        db_session, text="repeated text", instruction_version=INSTRUCTION_VERSION,
        check_fn=check_fn,
    )

    assert outcome.hit is True
    assert check_fn.calls["count"] == 1
    assert allowed is False


async def test_matching_signature_but_different_instruction_version_is_a_miss(db_session):
    check_fn = _check_fn(result=True)
    await get_or_check_moderation(
        db_session, text="repeated text", instruction_version="v1", check_fn=check_fn
    )
    db_session.commit()

    _, outcome = await get_or_check_moderation(
        db_session, text="repeated text", instruction_version="v2", check_fn=check_fn
    )

    assert outcome.hit is False
    assert check_fn.calls["count"] == 2


async def test_case_and_whitespace_only_differences_hash_the_same(db_session):
    check_fn = _check_fn(result=True)
    await get_or_check_moderation(
        db_session, text="  Photosynthesis Needs Light  ", instruction_version=INSTRUCTION_VERSION,
        check_fn=check_fn,
    )
    db_session.commit()

    _, outcome = await get_or_check_moderation(
        db_session, text="photosynthesis needs light", instruction_version=INSTRUCTION_VERSION,
        check_fn=check_fn,
    )

    assert outcome.hit is True
    assert check_fn.calls["count"] == 1


async def test_different_texts_never_collide(db_session):
    check_fn = _check_fn(result=True)
    await get_or_check_moderation(
        db_session, text="first text", instruction_version=INSTRUCTION_VERSION, check_fn=check_fn
    )
    db_session.commit()

    _, outcome = await get_or_check_moderation(
        db_session, text="second, unrelated text", instruction_version=INSTRUCTION_VERSION,
        check_fn=check_fn,
    )

    assert outcome.hit is False
    assert check_fn.calls["count"] == 2


async def test_lookup_failure_is_a_miss_and_check_fn_still_runs(db_session, monkeypatch):
    check_fn = _check_fn(result=True)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(db_session, "query", _boom)

    allowed, outcome = await get_or_check_moderation(
        db_session, text="whatever", instruction_version=INSTRUCTION_VERSION, check_fn=check_fn
    )

    assert outcome.hit is False
    assert outcome.reason == "storage_failure"
    assert check_fn.calls["count"] == 1
    assert allowed is True


async def test_storage_failure_does_not_poison_the_session_for_later_queries(
    db_session, monkeypatch
):
    """Principle IX/FR-006 PR feedback: on Postgres, a failed statement
    aborts the whole transaction -- `get_or_check_moderation` scopes
    every risky operation inside its own `db.begin_nested()` SAVEPOINT
    specifically so a real, later query/commit on this same (shared
    request) session still succeeds instead of raising
    `PendingRollbackError`."""
    check_fn = _check_fn(result=True)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(db_session, "query", _boom)

    _, outcome = await get_or_check_moderation(
        db_session, text="whatever", instruction_version=INSTRUCTION_VERSION, check_fn=check_fn
    )
    assert outcome.reason == "storage_failure"

    monkeypatch.undo()  # restore the real db.query to prove the session recovered
    assert db_session.query(ModerationCache).count() == 1
    db_session.commit()  # must not raise PendingRollbackError


async def test_inserted_row_never_stores_the_raw_submitted_text(db_session):
    check_fn = _check_fn(result=True)
    raw_text = "this exact string must never appear in a stored column"

    await get_or_check_moderation(
        db_session, text=raw_text, instruction_version=INSTRUCTION_VERSION, check_fn=check_fn
    )
    db_session.commit()

    row = db_session.query(ModerationCache).one()
    stored_values = [str(value) for value in vars(row).values()]
    assert not any(raw_text in value for value in stored_values)
