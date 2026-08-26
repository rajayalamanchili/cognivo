"""Unit test: `src/agent.py`'s `_streaming_request_converter` actually
forces `StreamingMode.SSE` on every run.

Found live against production (roadmap.md's Milestone 9 status):
`to_a2a()`'s own default request converter builds every run with
google-adk's default `RunConfig` (`streaming_mode=StreamingMode.NONE`),
so the underlying Claude call was never asked to stream -- every
exchange arrived as one buffered chunk, and its Langfuse generation
span had no "time to first token" at all. `to_a2a()` exposes no direct
`run_config` kwarg; `_streaming_request_converter` (wired in via
`agent_executor_factory`) is the one hook ADK provides to override it.
"""

import os

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-test-only")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-test-only")

from unittest.mock import patch  # noqa: E402

from google.adk.a2a.converters.request_converter import AgentRunRequest  # noqa: E402
from google.adk.agents.run_config import RunConfig, StreamingMode  # noqa: E402
from google.genai import types as genai_types  # noqa: E402

from src.agent import _streaming_request_converter  # noqa: E402


def test_forces_sse_streaming_mode():
    base_request = AgentRunRequest(
        user_id="learner",
        session_id="session-1",
        new_message=genai_types.Content(role="user", parts=[]),
        run_config=RunConfig(custom_metadata={"a2a_metadata": {"foo": "bar"}}),
    )
    with patch("src.agent.convert_a2a_request_to_agent_run_request", return_value=base_request):
        result = _streaming_request_converter(request=object(), part_converter=object())

    assert result.run_config.streaming_mode == StreamingMode.SSE


def test_preserves_custom_metadata_while_forcing_streaming():
    base_request = AgentRunRequest(
        run_config=RunConfig(custom_metadata={"a2a_metadata": {"foo": "bar"}}),
    )
    with patch("src.agent.convert_a2a_request_to_agent_run_request", return_value=base_request):
        result = _streaming_request_converter(request=object(), part_converter=object())

    assert result.run_config.custom_metadata == {"a2a_metadata": {"foo": "bar"}}
