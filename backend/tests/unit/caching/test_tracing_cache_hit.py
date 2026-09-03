"""Unit test: `record_cache_hit_trace()` emits a generation-shaped
Langfuse observation with zero token usage (spec 015 FR-013,
research.md §4) -- `traced_request()` alone creates no span for a cache
hit (no real ADK call happens), so this is the explicit mechanism that
makes a hit exactly as traceable as a fresh model call.

Mocks `get_client()` directly (mirrors `test_misconception_embed.py`'s
pure-unit-test style) rather than wiring a real Langfuse/OTel pipeline
-- `test_tracing_metadata_propagation.py` already covers the real,
ADK-instrumented span-attribute path; this only needs to confirm
`record_cache_hit_trace()` calls the manual v4 API with the right shape.
"""

import uuid
from unittest.mock import MagicMock, patch

from src.observability.tracing import record_cache_hit_trace


def test_starts_a_generation_shaped_observation_with_zero_usage():
    mock_generation = MagicMock()
    mock_client = MagicMock()
    mock_client.start_observation.return_value = mock_generation
    cache_entry_id = uuid.uuid4()

    with (
        patch("src.observability.tracing.configure_tracing"),
        patch("src.observability.tracing.get_client", return_value=mock_client),
    ):
        record_cache_hit_trace(
            name="question_generation_cache_hit",
            cache_type="question_generation",
            cache_entry_id=cache_entry_id,
            prompt_version="v1",
            learner_id="learner-abc-123",
        )

    mock_client.start_observation.assert_called_once()
    call_kwargs = mock_client.start_observation.call_args.kwargs
    assert call_kwargs["name"] == "question_generation_cache_hit"
    assert call_kwargs["as_type"] == "generation"
    assert call_kwargs["usage_details"] == {"input": 0, "output": 0}
    assert call_kwargs["metadata"] == {
        "cache_type": "question_generation",
        "cache_entry_id": str(cache_entry_id),
        "prompt_version": "v1",
        "learner_id": "learner-abc-123",
    }
    mock_generation.end.assert_called_once()
