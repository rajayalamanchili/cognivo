"""Langfuse + OpenInference tracing for the Tutor Agent's LLM call
(CLAUDE.md: "every agent invocation must emit a Langfuse trace... this
is separate from, and in addition to, the pedagogical audit log", FR-008).

Duplicated from (not imported from) `backend/src/observability/
tracing.py` and `grading-agent/src/tracing.py` -- `tutor-agent/` is a
genuinely separate deployable unit with its own dependency set
(research.md §2), same reasoning `grading-agent/src/tracing.py`'s
module docstring already gives for not importing across a project
boundary. Reads the same `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/
`LANGFUSE_HOST` env vars the backend and Grading Agent do.

Vercel's Python Functions can be frozen or torn down immediately after
a response is sent, so spans must be explicitly flushed before the
response returns rather than relying on a background exporter thread --
this matters even more here than for Grading Agent, since a streamed
response's connection can stay open for the whole answer duration
(SC-001/SC-004).
"""

from langfuse import get_client
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

_instrumented = False


def configure_tracing() -> None:
    """Idempotently wire GoogleADKInstrumentor to Langfuse's OTel tracer.

    `get_client()` reads the Langfuse env vars and registers itself as
    the global OpenTelemetry tracer provider; `GoogleADKInstrumentor().
    instrument()` then auto-instruments the Tutor Agent's `LlmAgent`
    call against that provider with no per-call code.
    """
    global _instrumented
    if _instrumented:
        return
    get_client()
    GoogleADKInstrumentor().instrument()
    _instrumented = True


def flush_traces() -> None:
    """Force-flush all buffered spans. Called after every HTTP request
    (`_TracingFlushMiddleware` in `agent.py`), not just at shutdown."""
    get_client().flush()
