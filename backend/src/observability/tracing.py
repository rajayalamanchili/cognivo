"""Langfuse + OpenInference tracing for every agent invocation (FR-014).

This is separate from, and in addition to, the pedagogical
`AssessmentEvent` audit log (`services/audit_log/writer.py`) --
Langfuse answers "what happened inside the model call" (inputs,
outputs, latency, token cost); `AssessmentEvent` answers "why this
decision" (Constitution Principle V).

Vercel's Python Functions can be frozen or torn down immediately after
a response is sent, so spans must be explicitly flushed before the
response returns rather than relying on a background exporter thread
to eventually deliver them -- `traced_request` below is the enforcement
point every API route should wrap its agent-invoking work in.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from langfuse import get_client
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

_instrumented = False


def configure_tracing() -> None:
    """Idempotently wire GoogleADKInstrumentor to Langfuse's OTel tracer.

    `get_client()` reads `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/
    `LANGFUSE_HOST` from the environment (backend/.env.example) and
    registers itself as the global OpenTelemetry tracer provider;
    `GoogleADKInstrumentor().instrument()` then auto-instruments every
    ADK agent/tool call against that provider with no per-call code.
    """
    global _instrumented
    if _instrumented:
        return
    get_client()
    GoogleADKInstrumentor().instrument()
    _instrumented = True


def flush_traces() -> None:
    """Force-flush all buffered spans. Call before a Function returns."""
    get_client().flush()


@contextmanager
def traced_request() -> Iterator[None]:
    """Wrap one request's agent-invoking work; flushes on every exit path.

    Usage in an API route:
        with traced_request():
            ... call Diagnostic/Sequencing/Assessment-Generation agents ...
    """
    configure_tracing()
    try:
        yield
    finally:
        flush_traces()
