"""Unit tests: `src/agent.py`'s `_TraceCorrelationMiddleware` reads the
`X-Tutor-Exchange-Id`/`X-Tutor-Session-Id` headers `tutor_agent_client/
client.py` sends and propagates them via `tracing.traced_exchange()`.

Found during the T038 grounding investigation (roadmap.md): this
service's own Langfuse trace had no link back to the backend's
`TutorExchange` row at all, and matching by question text + rough
timestamp turned out to be unreliable enough to block root-causing a
real grounding failure -- these tests cover the header-extraction half
of the fix; `test_tracing_metadata_propagation.py` covers that
`traced_exchange()` itself actually lands the metadata on real spans.
"""

import os

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-test-only")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-test-only")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from src.agent import _TraceCorrelationMiddleware  # noqa: E402


def _http_scope(headers: list[tuple[bytes, bytes]]) -> dict:
    return {"type": "http", "headers": headers}


_EXCHANGE_ID = "12345678-1234-5678-1234-567812345678"
_SESSION_ID = "87654321-4321-8765-4321-876543214321"


@pytest.mark.asyncio
async def test_extracts_exchange_and_session_id_from_headers():
    calls = []

    async def fake_app(scope, receive, send):
        calls.append("app called")

    middleware = _TraceCorrelationMiddleware(fake_app)
    scope = _http_scope(
        [
            (b"x-tutor-exchange-id", _EXCHANGE_ID.encode()),
            (b"x-tutor-session-id", _SESSION_ID.encode()),
        ]
    )

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(exchange_id=_EXCHANGE_ID, session_id=_SESSION_ID)
    assert calls == ["app called"]


@pytest.mark.asyncio
async def test_missing_headers_propagate_as_none():
    async def fake_app(scope, receive, send):
        pass

    middleware = _TraceCorrelationMiddleware(fake_app)
    scope = _http_scope([])

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(exchange_id=None, session_id=None)


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
            (b"x-tutor-exchange-id", b"'; DROP TABLE tutor_exchanges; --"),
            (b"x-tutor-session-id", b"not-a-uuid-either"),
        ]
    )

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(exchange_id=None, session_id=None)


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
