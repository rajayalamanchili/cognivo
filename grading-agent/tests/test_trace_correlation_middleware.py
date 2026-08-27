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


@pytest.mark.asyncio
async def test_extracts_question_and_learner_id_from_headers():
    calls = []

    async def fake_app(scope, receive, send):
        calls.append("app called")

    middleware = _TraceCorrelationMiddleware(fake_app)
    scope = _http_scope(
        [
            (b"x-grading-question-id", b"question-abc-123"),
            (b"x-grading-learner-id", b"learner-xyz"),
        ]
    )

    with patch("src.agent.traced_exchange") as mock_traced_exchange:
        await middleware(scope, None, None)

    mock_traced_exchange.assert_called_once_with(
        question_id="question-abc-123", learner_id="learner-xyz"
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
