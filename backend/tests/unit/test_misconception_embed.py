"""Unit test: `embed.py`'s `embed_answer` retries once on a transient
embedding-provider failure, then raises `EmbeddingUnavailableError` once
`MAX_ATTEMPTS` is exhausted -- mirroring `passage_search.py`'s
`_embed_query` (`test_embed_query_retry.py`), the pattern this module
reuses (research.md §1).

No database dependency -- `embed_answer` is a pure wrapper around
`litellm.embedding`.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.services.misconception.embed import EmbeddingUnavailableError, embed_answer


def test_succeeds_on_first_attempt():
    fake_response = SimpleNamespace(data=[{"embedding": [0.1, 0.2]}])
    with patch("litellm.embedding", new=Mock(return_value=fake_response)):
        embedding = embed_answer("What is the slope?", "The slope is 3.")
    assert embedding == [0.1, 0.2]


def test_retries_once_then_succeeds():
    fake_response = SimpleNamespace(data=[{"embedding": [0.3, 0.4]}])
    mock_embedding = Mock(side_effect=[RuntimeError("transient"), fake_response])
    with patch("litellm.embedding", new=mock_embedding):
        embedding = embed_answer("What is the slope?", "The slope is 3.")
    assert embedding == [0.3, 0.4]
    assert mock_embedding.call_count == 2


def test_raises_embedding_unavailable_after_exhausting_retries():
    mock_embedding = Mock(side_effect=RuntimeError("Voyage 429: rate limited"))
    with patch("litellm.embedding", new=mock_embedding):
        with pytest.raises(EmbeddingUnavailableError) as exc_info:
            embed_answer("What is the slope?", "The slope is 3.")
    assert mock_embedding.call_count == 2
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_embeds_question_and_answer_together():
    fake_response = SimpleNamespace(data=[{"embedding": [0.5]}])
    mock_embedding = Mock(return_value=fake_response)
    with patch("litellm.embedding", new=mock_embedding):
        embed_answer("What is the slope?", "The slope is 3.")
    call_kwargs = mock_embedding.call_args.kwargs
    assert "What is the slope?" in call_kwargs["input"][0]
    assert "The slope is 3." in call_kwargs["input"][0]
