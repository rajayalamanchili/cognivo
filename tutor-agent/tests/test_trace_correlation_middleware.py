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


@pytest.mark.asyncio
async def test_extracts_exchange_and_session_id_from_headers():
    calls = []

    async def fake_app(scope, receive, send):
        calls.append("app called")

    middleware = _TraceCorrelationMiddleware(fake_app)
    scope = _http_scope(
        [
            (b"x-tutor-exchange-id", b"exchange-abc-123"),
            (b"x-tutor-session-id", b"session-xyz"),
        ]
    )

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(
        exchange_id="exchange-abc-123", session_id="session-xyz"
    )
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
async def test_non_http_scope_passes_through_without_tracing():
    calls = []

    async def fake_app(scope, receive, send):
        calls.append("app called")

    middleware = _TraceCorrelationMiddleware(fake_app)

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware({"type": "lifespan"}, None, None)

    mock_traced_exchange.assert_not_called()
    assert calls == ["app called"]
