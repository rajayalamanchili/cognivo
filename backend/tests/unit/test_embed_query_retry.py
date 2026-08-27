"""Unit test: `passage_search.py`'s `_embed_query` retries once on a
transient embedding-provider failure, then raises `EmbeddingUnavailableError`
once `MAX_ATTEMPTS` is exhausted -- rather than letting the raw provider
exception propagate uncaught (found live, T038 grounding investigation,
roadmap.md: a Voyage account with no payment method caps embedding calls
at 3 RPM, and every 429 past that cap previously vanished as an
unhandled 500 with no `TutorExchange` row, no audit-log event, nothing).

No database dependency -- `_embed_query` is a pure wrapper around
`litellm.aembedding`.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services.retrieval.passage_search import EmbeddingUnavailableError, _embed_query


async def test_succeeds_on_first_attempt():
    fake_response = SimpleNamespace(data=[{"embedding": [0.1, 0.2]}])
    with patch("litellm.aembedding", new=AsyncMock(return_value=fake_response)):
        embedding = await _embed_query("a question")
    assert embedding == [0.1, 0.2]


async def test_retries_once_then_succeeds():
    fake_response = SimpleNamespace(data=[{"embedding": [0.3, 0.4]}])
    mock_aembedding = AsyncMock(side_effect=[RuntimeError("transient"), fake_response])
    with patch("litellm.aembedding", new=mock_aembedding):
        embedding = await _embed_query("a question")
    assert embedding == [0.3, 0.4]
    assert mock_aembedding.call_count == 2


async def test_raises_embedding_unavailable_after_exhausting_retries():
    mock_aembedding = AsyncMock(side_effect=RuntimeError("Voyage 429: rate limited"))
    with patch("litellm.aembedding", new=mock_aembedding):
        with pytest.raises(EmbeddingUnavailableError) as exc_info:
            await _embed_query("a question")
    assert mock_aembedding.call_count == 2
    # The real cause stays chained, not swallowed -- this is what let
    # this session's own live investigation find the Voyage rate-limit
    # root cause from Vercel's logged traceback.
    assert isinstance(exc_info.value.__cause__, RuntimeError)
