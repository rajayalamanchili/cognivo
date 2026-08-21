"""Grading Agent (spec 007 FR-003) -- this project's first remote A2A
service, not a local ADK sub-agent (research.md §1/§2).

Deployed as its own Vercel project (plan.md's Project Structure), with
no database connection of its own (research.md §3) -- it is a pure
function of its A2A request (question rubric + learner answer in,
graduated score + criteria breakdown + Grading Logic Version out). The
calling backend (`backend/src/services/grading_client/`) is solely
responsible for validating this agent's response (FR-014) and
persisting it -- this module never writes to a database.
"""

import hmac
import os
from collections.abc import Sequence

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.guardrails import before_model_guardrail
from src.prompt_defense import build_instruction
from src.tracing import configure_tracing, flush_traces

APP_NAME = "cognivo-grading-agent"

# Bumped whenever this agent's scoring prompt/logic changes (FR-008's
# ground-truth eval gate protects any such change before it ships).
# A code constant, not a database row (research.md §8) -- git history is
# the audit trail for when/why this changed.
GRADING_LOGIC_VERSION = "v1"


class CriterionResult(BaseModel):
    """One rubric criterion's grading outcome (contracts/api.md)."""

    description: str
    met: bool


class GradingResult(BaseModel):
    """The Grading Agent's structured A2A response shape (contracts/api.md).

    The caller (`services/grading_client/client.py`) validates this
    against the question's own rubric -- same criteria count/order,
    score in range -- before ever accepting it (FR-014); this schema
    only guarantees the *shape* is well-formed, not that the *content*
    is trustworthy.
    """

    graduated_score: float = Field(ge=0.0, le=1.0)
    criteria_results: list[CriterionResult]
    grading_logic_version: str


def _build_agent(model_name: str) -> LlmAgent:
    return LlmAgent(
        name="grading_agent",
        model=LiteLlm(model=model_name),
        instruction=build_instruction(grading_logic_version=GRADING_LOGIC_VERSION),
        output_schema=GradingResult,
        # Compensating control for a leaked GRADING_AGENT_SHARED_SECRET
        # (guardrails.py) -- the backend's own length/moderation checks
        # only run for requests that go through the backend; a leaked
        # secret bypasses it entirely.
        before_model_callback=before_model_guardrail,
    )


# Constructed once at import time (unlike assessment_gen/agent.py's
# per-call `_build_agent`, this agent's instruction is fixed and
# request-independent -- see prompt_defense.py) because `to_a2a()` needs
# a module-level ASGI `app` object for Vercel's Python runtime to find
# (research.md §1). Falls back to the same default model
# `ASSESSMENT_GEN_MODEL` uses in `backend/.env.example` so importing
# this module never crashes when the env var isn't set (e.g. during
# lint/test collection); real grading calls should set
# `GRADING_AGENT_MODEL` explicitly.
_MODEL_NAME = os.environ.get("GRADING_AGENT_MODEL", "anthropic/claude-sonnet-4-5")
_agent = _build_agent(_MODEL_NAME)

# Instruments every ADK agent/tool call globally (idempotent), same as
# the backend's `traced_request()` does per-request (CLAUDE.md: "every
# agent invocation must emit a Langfuse trace", PR #18 review -- this
# agent previously had no tracing dependency or call at all). Safe to
# do once here rather than per-request: `GoogleADKInstrumentor.
# instrument()` patches the ADK call sites globally, not per `LlmAgent`
# instance, so it only needs to run before the first request is served.
configure_tracing()


class _SharedSecretAuthMiddleware:
    """Rejects any HTTP request that doesn't carry a recognized shared
    secret in `X-Grading-Agent-Secret` (PR #18 review).

    This agent is deployed as its own public Vercel project
    (research.md §2), and the backend's own guardrails (length cap, rate
    limit, moderation) don't run inside this service -- they're
    deliberately backend-only, "platform-wide abuse-prevention... not
    duplicated per-agent" (plan.md's Constitution Principle IV table).
    That split only holds for requests actually routed through the
    backend, so without this check anyone with the URL could call this
    endpoint directly and bypass every one of them. The backend attaches
    this same header on every call (`grading_client/client.py`). Fails
    closed if no secret is configured -- a misconfigured deployment
    should refuse traffic, not silently run unauthenticated.

    This is the primary control, not the only one: `guardrails.py`'s
    `before_model_guardrail` (wired via `before_model_callback` in
    `_build_agent`) re-checks length and moderation *inside* this agent
    too, as a compensating control for the case this secret itself
    leaks -- see that module's docstring.

    Accepts up to two valid secrets at once (`GRADING_AGENT_SHARED_
    SECRET` and an optional `GRADING_AGENT_SHARED_SECRET_NEXT`,
    tech-stack.md's "A2A secret rotation" row, Constitution Principle
    VI v1.5.0) so a rotation is set-next -> confirm the backend's calls
    with the new secret succeed -> promote next to current on this
    deployment -> remove the old value from the backend, rather than a
    single cutover that requires this agent's and the backend's
    independently-deployed Vercel projects to redeploy in the same
    instant.
    """

    def __init__(self, app: ASGIApp, expected_secrets: Sequence[str]) -> None:
        self._app = app
        self._expected_secrets = [secret for secret in expected_secrets if secret]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        provided = headers.get(b"x-grading-agent-secret", b"").decode("utf-8", errors="replace")
        # hmac.compare_digest per candidate, not `in`/`==` -- this is a
        # public endpoint (PR #18 review), and a plain string comparison
        # short-circuits on the first mismatched byte, a timing
        # side-channel against the secret.
        if not self._expected_secrets or not any(
            hmac.compare_digest(provided, secret) for secret in self._expected_secrets
        ):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)


class _TracingFlushMiddleware:
    """Force-flushes buffered Langfuse spans after every HTTP request.

    Vercel's Python Functions can be frozen or torn down immediately
    after a response is sent, so this can't rely on a background
    exporter thread eventually delivering spans -- same reasoning as
    the backend's `traced_request()` (`tracing.py`).
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        try:
            await self._app(scope, receive, send)
        finally:
            flush_traces()


app = _TracingFlushMiddleware(
    _SharedSecretAuthMiddleware(
        to_a2a(_agent),
        expected_secrets=(
            os.environ.get("GRADING_AGENT_SHARED_SECRET", ""),
            os.environ.get("GRADING_AGENT_SHARED_SECRET_NEXT", ""),
        ),
    )
)
