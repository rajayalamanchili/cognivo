"""Integration test: `traced_request(learner_id=..., session_id=...)`
actually lands `metadata.learner_id`/`metadata.session_id` on every
span an agent invocation produces (Langfuse v4 migration).

Uses a real `LangfuseSpanProcessor` (constructed directly with an
in-memory `span_exporter`, bypassing the network-based OTLP exporter
entirely -- no live Langfuse account needed) rather than a bare OTel
`TracerProvider`, unlike `test_tracing_completeness.py`'s harness --
that processor's `on_start()` is what actually reads
`propagate_attributes()`'s context and writes it onto each span, so a
bare provider (no `LangfuseSpanProcessor` attached) would silently
prove nothing about propagation either way.

This test exists because `propagate_attributes(user_id=..., session_id
=...)` (the v3->v4 guide's own example shape) does NOT survive on this
project's actual spans: `GoogleADKInstrumentor` sets its own `user.id`/
`session.id` attributes from the ADK `Runner`'s own `user_id`/
`session_id` arguments, on the same OTel attribute keys, *after*
`LangfuseSpanProcessor.on_start()` has already applied the propagated
ones -- discovered only by inspecting real captured span attributes,
not by reading either library's docs. `traced_request()` therefore
propagates via `metadata=` instead (`src/observability/tracing.py`'s
module docstring has the full finding); this test is what would catch
a regression back to the colliding native fields.
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

import src.observability.tracing as tracing_module
from src.observability.tracing import traced_request

APP_NAME = "cognivo-tracing-metadata-propagation-test"


class _FakeLlm(BaseLlm):
    """Mirrors `test_tracing_completeness.py`'s fake model -- exercises
    the real `Runner.run_async`/`BaseAgent.run_async` methods
    `GoogleADKInstrumentor` wraps, without needing a live LLM API key.
    """

    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="ok")]),
            partial=False,
        )


@pytest.fixture()
def in_memory_langfuse_tracing():
    """Instruments `GoogleADKInstrumentor` against a `TracerProvider`
    that has a *real* `LangfuseSpanProcessor` attached (constructed with
    an in-memory `span_exporter` so nothing goes over the network) --
    the actual object that applies `propagate_attributes()`'s context
    onto each span, unlike `test_tracing_completeness.py`'s bare
    `SimpleSpanProcessor`-only provider.
    """
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
    # A second, plain processor so this test can inspect spans directly
    # via its own exporter without relying on LangfuseSpanProcessor's
    # (network-oriented) batching/export-filtering behavior.
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
async def test_learner_and_session_metadata_propagate_to_every_span(
    in_memory_langfuse_tracing,
):
    session_service = InMemorySessionService()

    with traced_request(learner_id="learner-abc-123", session_id="tutoring-session-xyz"):
        await _run_one_agent_invocation(session_service)

    spans = in_memory_langfuse_tracing.get_finished_spans()
    assert spans, "expected at least one span from the agent invocation"

    for span in spans:
        attributes = span.attributes or {}
        assert (
            attributes.get("langfuse.trace.metadata.learner_id") == "learner-abc-123"
        ), f"span {span.name!r} missing propagated learner_id metadata: {dict(attributes)}"
        assert (
            attributes.get("langfuse.trace.metadata.session_id") == "tutoring-session-xyz"
        ), f"span {span.name!r} missing propagated session_id metadata: {dict(attributes)}"


@pytest.mark.asyncio
async def test_no_learner_id_means_no_metadata_written(in_memory_langfuse_tracing):
    """`traced_request()` with no `learner_id` (its default) must not
    write empty/placeholder metadata -- callers with no learner context
    (none exist today, but the parameter is optional) shouldn't pollute
    every span with `metadata.learner_id=None`."""
    session_service = InMemorySessionService()

    with traced_request():
        await _run_one_agent_invocation(session_service)

    spans = in_memory_langfuse_tracing.get_finished_spans()
    assert spans, "expected at least one span from the agent invocation"
    for span in spans:
        attributes = span.attributes or {}
        assert "langfuse.trace.metadata.learner_id" not in attributes
        assert "langfuse.trace.metadata.session_id" not in attributes
