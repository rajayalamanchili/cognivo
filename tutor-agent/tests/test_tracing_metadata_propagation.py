"""Integration test: `tracing.traced_exchange(exchange_id=..., session_id
=...)` actually lands `metadata.exchange_id`/`metadata.session_id` on
every span an agent invocation produces.

Mirrors `backend/tests/integration/test_tracing_metadata_propagation.py`'s
harness exactly (same `LangfuseSpanProcessor`-attached `TracerProvider`
reasoning: a bare provider would prove nothing about propagation). Exists
because this service's Langfuse trace previously had no link back to the
backend's `TutorExchange` row at all (found during the T038 grounding
investigation, roadmap.md) -- `traced_exchange()` closes that gap the
same way `traced_request()` already does on the backend side.
"""

from collections.abc import AsyncGenerator

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import src.tracing as tracing_module
from src.tracing import traced_exchange

APP_NAME = "cognivo-tutor-agent-tracing-metadata-propagation-test"


class _FakeLlm(BaseLlm):
    """Mirrors the backend test's fake model -- exercises the real
    `Runner.run_async`/`BaseAgent.run_async` methods `GoogleADKInstrumentor`
    wraps, without needing a live LLM API key."""

    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="ok")]),
            partial=False,
        )


@pytest.fixture()
def in_memory_langfuse_tracing():
    from langfuse._client.span_processor import LangfuseSpanProcessor

    exporter = InMemorySpanExporter()
    langfuse_processor = LangfuseSpanProcessor(
        public_key="pk-test-only",
        secret_key="sk-test-only",
        base_url="http://unused.invalid",
        span_exporter=exporter,
    )
    provider = TracerProvider()
    provider.add_span_processor(langfuse_processor)
    passthrough_exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(passthrough_exporter))

    instrumentor = GoogleADKInstrumentor()
    if getattr(instrumentor, "_is_instrumented_by_opentelemetry", False):
        instrumentor.uninstrument()
    instrumentor.instrument(tracer_provider=provider)

    previous_instrumented_flag = tracing_module._instrumented
    tracing_module._instrumented = True

    try:
        yield passthrough_exporter
    finally:
        instrumentor.uninstrument()
        tracing_module._instrumented = previous_instrumented_flag
        langfuse_processor.shutdown()


async def _run_one_agent_invocation(session_service: InMemorySessionService) -> None:
    agent = LlmAgent(
        name="fake_agent",
        model=_FakeLlm(model="fake-model"),
        instruction="Respond with anything.",
    )
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    user_id = "tracing-metadata-test"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text="go")])

    async for _event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        pass


@pytest.mark.asyncio
async def test_exchange_and_session_metadata_propagate_to_every_span(
    in_memory_langfuse_tracing,
):
    session_service = InMemorySessionService()

    with traced_exchange(exchange_id="exchange-abc-123", session_id="tutoring-session-xyz"):
        await _run_one_agent_invocation(session_service)

    spans = in_memory_langfuse_tracing.get_finished_spans()
    assert spans, "expected at least one span from the agent invocation"

    for span in spans:
        attributes = span.attributes or {}
        assert (
            attributes.get("langfuse.trace.metadata.exchange_id") == "exchange-abc-123"
        ), f"span {span.name!r} missing propagated exchange_id metadata: {dict(attributes)}"
        assert (
            attributes.get("langfuse.trace.metadata.session_id") == "tutoring-session-xyz"
        ), f"span {span.name!r} missing propagated session_id metadata: {dict(attributes)}"


@pytest.mark.asyncio
async def test_no_exchange_id_means_no_metadata_written(in_memory_langfuse_tracing):
    """No `exchange_id` (an unauthenticated request never reaches
    `_TraceCorrelationMiddleware`'s header extraction with a real value)
    must not write empty/placeholder metadata onto every span."""
    session_service = InMemorySessionService()

    with traced_exchange(exchange_id=None, session_id=None):
        await _run_one_agent_invocation(session_service)

    spans = in_memory_langfuse_tracing.get_finished_spans()
    assert spans, "expected at least one span from the agent invocation"
    for span in spans:
        attributes = span.attributes or {}
        assert "langfuse.trace.metadata.exchange_id" not in attributes
        assert "langfuse.trace.metadata.session_id" not in attributes
