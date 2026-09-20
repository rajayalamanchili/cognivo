"""Unit tests: `issue_handoff_token`/`verify_handoff_token` (spec 019
FR-005a/b/c, research.md Decision 4).

Uses `monkeypatch` on the module's own internals (never touches real
env vars directly) to exercise expiry and wrong-signature cases.
"""

import datetime
import uuid

import pytest

from src.services.auth import tokens


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-do-not-use-in-production")


def test_round_trips_to_its_quiz_session_id():
    quiz_session_id = uuid.uuid4()
    token = tokens.issue_handoff_token(quiz_session_id)
    assert tokens.verify_handoff_token(token) == quiz_session_id


def test_expired_token_is_rejected(monkeypatch):
    monkeypatch.setattr(tokens, "_HANDOFF_TOKEN_TTL", datetime.timedelta(seconds=-1))
    already_expired = tokens.issue_handoff_token(uuid.uuid4())
    assert tokens.verify_handoff_token(already_expired) is None


def test_malformed_token_is_rejected():
    assert tokens.verify_handoff_token("not-a-real-token") is None


def test_wrong_signature_is_rejected(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(tokens, "_secret", lambda: "a-completely-different-signing-key")
        forged = tokens.issue_handoff_token(uuid.uuid4())
    assert tokens.verify_handoff_token(forged) is None


def test_wrong_token_type_is_rejected():
    """A real login session JWT must never be accepted as a hand-off
    token, even though both are signed with the same key."""
    login_token = tokens.issue_token(account_type="guardian", account_id=uuid.uuid4())
    assert tokens.verify_handoff_token(login_token) is None
