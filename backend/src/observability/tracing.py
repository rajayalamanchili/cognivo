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

v4 note: this project's only instrumentation is `GoogleADKInstrumentor`
(`openinference.instrumentation.google_adk`, scope name
`"openinference.instrumentation.google_adk"`), which matches v4's
default `should_export_span` filter's `"openinference"` prefix
unmodified -- verified directly against `langfuse._client.span_filter
.is_known_llm_instrumentor` (no real spans in this codebase come from
any other scope), so no `should_export_span` override is needed here.

`traced_request()`'s `learner_id`/`session_id` params use v4's
`propagate_attributes()`, but deliberately via `metadata=` rather than
the native `user_id=`/`session_id=` kwargs the v3->v4 guide's example
shows. Verified directly with an in-memory OTel exporter:
`GoogleADKInstrumentor` sets its own `user.id`/`session.id` span
attributes from the ADK `Runner`'s own `user_id`/`session_id`
arguments -- the exact same OTel attribute keys
`propagate_attributes(user_id=..., session_id=...)` would write to --
and does so *after* Langfuse's `LangfuseSpanProcessor.on_start()` has
already applied the propagated ones, so the ADK-native value always
wins and the propagated one is silently lost. `metadata=` uses a
disjoint key namespace (`langfuse.trace.metadata.*`) that ADK's own
instrumentation never touches, so it survives -- confirmed present on
every span this repo's instrumentation actually produces. Fixing the
native `user_id`/`session_id` fields properly would mean passing the
real learner id into every `Runner.run_async`/`session_service
.create_session(user_id=...)` call across this codebase (several of
which currently pass a fixed per-service placeholder string, e.g.
`assessment_gen/agent.py`'s `"assessment-gen-service"`) -- a broader
change than this SDK migration, left as a follow-up rather than made
silently here.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from langfuse import get_client, propagate_attributes
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
def traced_request(
    *,
    learner_id: uuid.UUID | str | None = None,
    session_id: uuid.UUID | str | None = None,
) -> Iterator[None]:
    """Wrap one request's agent-invoking work; flushes on every exit path.

    `learner_id`/`session_id`, when given, are propagated (via v4's
    `propagate_attributes()`, module docstring) as trace metadata to
    every span this block creates -- lets a specific learner's or
    tutoring/quiz session's traces be found/filtered in Langfuse by
    `metadata.learner_id`/`metadata.session_id`, matching Constitution
    Principle V's "why was I shown this" answer at the observability
    layer too, not just the audit log. Omit `session_id` for a call
    with no bounded-session concept (e.g. placement); every call site
    here always has a `learner_id`.

    Usage in an API route:
        with traced_request(learner_id=learner_id):
            ... call Diagnostic/Sequencing/Assessment-Generation agents ...
    """
    configure_tracing()
    try:
        if learner_id is not None:
            metadata = {"learner_id": str(learner_id)}
            if session_id is not None:
                metadata["session_id"] = str(session_id)
            with propagate_attributes(metadata=metadata):
                yield
        else:
            yield
    finally:
        flush_traces()


def record_cache_hit_trace(
    *,
    name: str,
    cache_type: str,
    cache_entry_id: uuid.UUID,
    prompt_version: str,
    learner_id: uuid.UUID | str,
) -> None:
    """Emits a generation-shaped Langfuse observation for one semantic-
    cache hit (spec 015 FR-013, research.md §4).

    `traced_request()` alone creates no span -- real spans in this
    codebase only come from `GoogleADKInstrumentor` auto-instrumenting a
    real ADK `Runner` call (module docstring above), and a cache hit
    makes none. This creates one explicitly, via the v4 client's manual
    `start_observation(as_type="generation")` API, so a cache hit is
    exactly as traceable as a fresh model call (Constitution Principle
    V), never silently untraced. `usage_details={"input": 0, "output":
    0}` makes the zero-token, no-model-call nature of a hit visible in
    Langfuse itself, rather than indistinguishable there from a real
    generation.

    Call this from inside the caller's existing `traced_request()` block
    (or, for the in-quiz question-generation path, which has no such
    block today, on its own -- `configure_tracing()` below is
    idempotent either way).
    """
    configure_tracing()
    generation = get_client().start_observation(
        name=name,
        as_type="generation",
        usage_details={"input": 0, "output": 0},
        metadata={
            "cache_type": cache_type,
            "cache_entry_id": str(cache_entry_id),
            "prompt_version": prompt_version,
            "learner_id": str(learner_id),
        },
    )
    generation.end()
