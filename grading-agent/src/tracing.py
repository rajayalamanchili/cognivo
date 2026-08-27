"""Langfuse + OpenInference tracing for the Grading Agent's LLM call
(CLAUDE.md: "every agent invocation must emit a Langfuse trace... this
is separate from, and in addition to, the pedagogical audit log").

Duplicated from (not imported from) `backend/src/observability/
tracing.py` -- `grading-agent/` is a genuinely separate deployable unit
with its own dependency set (research.md §2), same reasoning
`scripts/eval_runner.py`'s module docstring already gives for not
importing across the `backend`/`grading-agent` boundary. Reads the same
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST` env vars the
backend does (`backend/.env.example`).

Vercel's Python Functions can be frozen or torn down immediately after
a response is sent, so spans must be explicitly flushed before the
response returns rather than relying on a background exporter thread.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from langfuse import get_client, propagate_attributes
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

_instrumented = False


def configure_tracing() -> None:
    """Idempotently wire GoogleADKInstrumentor to Langfuse's OTel tracer.

    `get_client()` reads the Langfuse env vars and registers itself as
    the global OpenTelemetry tracer provider; `GoogleADKInstrumentor().
    instrument()` then auto-instruments the Grading Agent's `LlmAgent`
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


@contextmanager
def traced_exchange(*, question_id: str | None, learner_id: str | None) -> Iterator[None]:
    """Propagates `question_id`/`learner_id` (read from the
    `X-Grading-Question-Id`/`X-Grading-Learner-Id` headers `grading_
    client/client.py` sends on every call) as trace metadata, via the
    same `propagate_attributes(metadata=...)` mechanism `backend/src/
    observability/tracing.py`'s `traced_request()` already uses.

    Without this, this service's own Langfuse trace had no link back to
    the backend's own `question_id`/`learner_id` at all -- the same gap
    found (and fixed the same way) in `tutor-agent/`'s copy of this
    function during the T038 grounding investigation, roadmap.md.
    `metadata=` (not the native `session_id=`/`user_id=` kwargs) for the
    same reason `traced_request()`'s docstring gives -- `GoogleADK
    Instrumentor` sets its own `session.id`/`user.id` span attributes
    from the ADK `Runner`'s own arguments, which would silently win over
    the native kwargs but never touches the `langfuse.trace.metadata.*`
    namespace `metadata=` writes to.
    """
    if question_id is None:
        yield
        return
    metadata = {"question_id": question_id}
    if learner_id is not None:
        metadata["learner_id"] = learner_id
    with propagate_attributes(metadata=metadata):
        yield
