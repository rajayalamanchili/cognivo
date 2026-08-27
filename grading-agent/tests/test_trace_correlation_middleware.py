"""Unit tests: `src/agent.py`'s `_TraceCorrelationMiddleware` reads the
`X-Grading-Question-Id`/`X-Grading-Learner-Id` headers `grading_client/
client.py` sends and propagates them via `tracing.traced_exchange()`.

Mirrors `tutor-agent/tests/test_trace_correlation_middleware.py` -- this
service had the identical A2A-hop-with-no-correlation-header gap (found
during the T038 grounding investigation, roadmap.md, and applied here
too since Grading Agent shares the same shape of client/agent split).
"""

import os

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-test-only")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-test-only")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from src.agent import _TraceCorrelationMiddleware  # noqa: E402


def _http_scope(headers: list[tuple[bytes, bytes]]) -> dict:
    return {"type": "http", "headers": headers}


_QUESTION_ID = "12345678-1234-5678-1234-567812345678"
_LEARNER_ID = "87654321-4321-8765-4321-876543214321"


@pytest.mark.asyncio
async def test_extracts_question_and_learner_id_from_headers():
    calls = []

    async def fake_app(scope, receive, send):
        calls.append("app called")

    middleware = _TraceCorrelationMiddleware(fake_app)
    scope = _http_scope(
        [
            (b"x-grading-question-id", _QUESTION_ID.encode()),
            (b"x-grading-learner-id", _LEARNER_ID.encode()),
        ]
    )

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(question_id=_QUESTION_ID, learner_id=_LEARNER_ID)
    assert calls == ["app called"]


@pytest.mark.asyncio
async def test_missing_headers_propagate_as_none():
    async def fake_app(scope, receive, send):
        pass

    middleware = _TraceCorrelationMiddleware(fake_app)
    scope = _http_scope([])

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(question_id=None, learner_id=None)


@pytest.mark.asyncio
async def test_malformed_header_values_propagate_as_none():
    """PR #38 review nit: a header value that isn't a real UUID (e.g. a
    leaked-secret attacker trying to inject arbitrary trace metadata)
    must be dropped, not passed through to `traced_exchange()` verbatim."""

    async def fake_app(scope, receive, send):
        pass

    middleware = _TraceCorrelationMiddleware(fake_app)
    scope = _http_scope(
        [
            (b"x-grading-question-id", b"'; DROP TABLE questions; --"),
            (b"x-grading-learner-id", b"not-a-uuid-either"),
        ]
    )

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(question_id=None, learner_id=None)


@pytest.mark.asyncio
async def test_non_http_scope_passes_through_without_tracing():
    calls = []

    async def fake_app(scope, receive, send):
        calls.append("app called")

    middleware = _TraceCorrelationMiddleware(fake_app)

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware({"type": "lifespan"}, None, None)

    mock_traced_exchange.assert_not_called()
    assert calls == ["app called"]
