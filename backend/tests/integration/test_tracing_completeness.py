"""Integration test: Langfuse trace count equals agent-invocation count,
no dropped spans (SC-008), T058.

Exercises the real instrumentation mechanism FR-014/SC-008 depend on --
`GoogleADKInstrumentor` wrapping `Runner.run_async`/`BaseAgent.run_async`,
and `traced_request()`'s explicit flush-before-return -- rather than
Diagnostic/Sequencing/Assessment-Generation specifically, since SC-008 is
a claim about the tracing pipeline for ANY agent invocation, not any one
agent's business logic (already covered by that agent's own tests).

Deliberately does not require a live Langfuse account: the OTel
`TracerProvider` `GoogleADKInstrumentor` attaches to is swapped for an
in-memory span exporter for the duration of the test (this is a test
double for "the observability backend" quickstart.md step 7 names, not a
weakening of the claim -- the spans it captures are the exact spans a
real Langfuse processor would receive). `SimpleSpanProcessor` exports
synchronously on span-end, so this test also does not depend on
`traced_request()`'s flush actually reaching a live network endpoint.
Does not need `DATABASE_URL` either -- unlike the other integration
tests in this suite, agent invocation here uses ADK's
`InMemorySessionService` directly rather than the DB-backed one the API
routes use, since SC-008 is about the tracing layer, not persistence.
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

APP_NAME = "cognivo-tracing-completeness-test"


class _FakeLlm(BaseLlm):
    """Minimal `BaseLlm` that always returns one canned text response --
    stands in for a real Diagnostic/Sequencing/Assessment-Generation
    agent's model call so `Runner.run_async`/`BaseAgent.run_async` (the
    exact methods `GoogleADKInstrumentor` wraps) execute for real,
    without needing a live LLM API key."""

    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="ok")]),
            partial=False,
        )


@pytest.fixture()
def in_memory_tracing():
    """Instruments `GoogleADKInstrumentor` against an in-memory OTel
    exporter for the duration of one test, regardless of whatever
    instrumentation state prior tests left behind -- explicit
    uninstall/reinstall makes this hermetic rather than relying on
    `GoogleADKInstrumentor`'s own idempotency guard picking up a stale
    tracer_provider from an earlier test or a real Langfuse call."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    instrumentor = GoogleADKInstrumentor()
    if getattr(instrumentor, "_is_instrumented_by_opentelemetry", False):
        instrumentor.uninstrument()
    instrumentor.instrument(tracer_provider=provider)

    previous_instrumented_flag = tracing_module._instrumented
    tracing_module._instrumented = True

    try:
        yield exporter
    finally:
        instrumentor.uninstrument()
        tracing_module._instrumented = previous_instrumented_flag


async def _run_one_agent_invocation(session_service: InMemorySessionService, index: int) -> None:
    agent = LlmAgent(
        name=f"fake_agent_{index}",
        model=_FakeLlm(model="fake-model"),
        instruction="Respond with anything.",
    )
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    user_id = "tracing-completeness-test"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text="go")])

    async for _event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        pass  # drain -- we only need the invocation to complete, not its content


@pytest.mark.asyncio
async def test_trace_count_matches_agent_invocation_count(in_memory_tracing):
    session_service = InMemorySessionService()
    num_invocations = 3

    with traced_request():
        for i in range(num_invocations):
            await _run_one_agent_invocation(session_service, i)

    spans = in_memory_tracing.get_finished_spans()
    agent_run_spans = [s for s in spans if s.name.startswith("agent_run")]

    assert len(agent_run_spans) == num_invocations, (
        f"expected one 'agent_run' span per agent invocation ({num_invocations}), "
        f"got {len(agent_run_spans)}: {[s.name for s in spans]}"
    )
    # No dropped spans: every agent_run span reached the exporter already
    # ended (SimpleSpanProcessor exports synchronously on span-end), and
    # traced_request()'s flush_traces() call did not raise.
    assert all(span.end_time is not None for span in agent_run_spans)
