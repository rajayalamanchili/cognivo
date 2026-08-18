"""Integration test: a `/recommendations` request emits zero Langfuse
spans, T021.

Deliberately documents a divergence from Milestone 1's own
SC-008 tracing-completeness test
(`tests/integration/test_tracing_completeness.py`), rather than
reproducing its "trace count equals invocation count" assertion:
`build_weak_area_report` makes no LLM/ADK `Runner`/`BaseAgent`
invocation at all (research.md §1), so `GoogleADKInstrumentor` --
tech-stack.md's locked, sole instrumentation mechanism -- has nothing
to instrument. Explainability for this agent is carried entirely by
the audit log (test_audit_log_completeness.py), not by tracing
(spec.md FR-008's amendment, discovered during this phase's
implementation). This test exists so that gap is proven with real
instrumentation active, not silently assumed.
"""

import pytest
from fastapi.testclient import TestClient
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import src.observability.tracing as tracing_module
from tests.integration.recommendation.scenarios import make_weak_topic


@pytest.fixture()
def in_memory_tracing():
    """Instruments `GoogleADKInstrumentor` against an in-memory OTel
    exporter for the duration of one test -- explicit uninstall/
    reinstall makes this hermetic regardless of whatever instrumentation
    state prior tests left behind."""
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


def test_recommendations_request_emits_no_agent_spans(
    in_memory_tracing, db_session, demo_learner, algebra_subject
):
    from src.api.main import app

    client = TestClient(app)
    learner_id = demo_learner.learner_id
    subject_id = algebra_subject.subject_id

    make_weak_topic(
        db_session,
        learner_id=learner_id,
        subject_id=subject_id,
        topic_id="order-of-operations",
        p_mastery=0.2,
    )

    response = client.get(
        f"/api/learners/{learner_id}/recommendations", params={"subject_id": subject_id}
    )
    assert response.status_code == 200, response.text

    spans = in_memory_tracing.get_finished_spans()
    agent_run_spans = [s for s in spans if s.name.startswith("agent_run")]

    assert agent_run_spans == [], (
        "expected zero agent_run spans for a fully-deterministic "
        f"Recommendation Agent request (research.md §1), got {[s.name for s in spans]}"
    )
