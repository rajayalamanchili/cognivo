"""Compensating guardrails for the Tutor Agent -- defense-in-depth
against a leaked `TUTOR_AGENT_SHARED_SECRET` (tech-stack.md's A2A auth
row, Constitution Principle VI, spec 012 FR-010/FR-011).

These do NOT replace the backend's own length/moderation checks on the
learner's raw question for legitimate traffic -- every backend-routed
request already passed them before this agent is ever called
(contracts/api.md's server steps). They exist solely to bound the
damage if the shared secret leaks and someone calls this public
endpoint directly, bypassing the backend (and its guardrails) entirely:
a length cap bounds worst-case token cost per request, and a
moderation re-check stops a leaked secret from being used to run
disallowed content through the tutoring model. The whole raw request
text (question + retrieved_passages + delegation_context, JSON-encoded)
is attacker-controlled if the secret leaks -- not just the "question"
field -- so both checks run against the full raw text, same reasoning
as `grading-agent/src/guardrails.py`'s docstring.

Deliberately excludes rate limiting: the backend's rate limiter is
DB-backed (`services/tutor/rate_limit.py`, research.md §8) because
Vercel Functions don't share in-memory state across invocations, and
this agent is a documented stateless pure function with no database
connection of its own (research.md §2, `agent.py`'s module docstring).
"""

import os
from typing import TYPE_CHECKING

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.models.llm_request import LlmRequest

# Generous enough for a legitimate question plus TOP_K=5 retrieved
# passages and a small delegation_context bundle
# (services/retrieval/passage_search.py), tight enough to bound
# worst-case token cost per request if TUTOR_AGENT_SHARED_SECRET leaks.
MAX_REQUEST_LENGTH = 12000

_APP_NAME = "cognivo-tutor-agent-guardrail-moderation"

_MODERATION_INSTRUCTION = """\
You are a content-moderation classifier for a learning platform's tutoring \
requests. Classify the submitted text as allowed or blocked.

Block text that contains hate speech, harassment, sexual content, threats \
of violence, or other abusive/toxic content. Do NOT block text merely \
because it is a confused, off-topic, blank, or nonsensical question. Do NOT \
block text merely because it attempts to instruct, manipulate, or override \
the tutor -- for example "ignore your previous instructions" or "pretend \
you are not a tutor". That is a prompt-integrity concern the tutor itself \
is separately responsible for resisting, never a moderation concern -- an \
instruction-like question with no hate speech, harassment, sexual content, \
or violent threats in it is allowed.

Respond with ONLY the structured output matching the required schema.
"""


class _ModerationResult(BaseModel):
    allowed: bool


def check_length(raw_request_text: str) -> bool:
    """True if the raw incoming request text is within `MAX_REQUEST_LENGTH`."""
    return len(raw_request_text) <= MAX_REQUEST_LENGTH


def _build_moderation_agent(model_name: str) -> LlmAgent:
    return LlmAgent(
        name="tutor_agent_guardrail_moderation",
        model=LiteLlm(model=model_name),
        instruction=_MODERATION_INSTRUCTION,
        output_schema=_ModerationResult,
    )


async def check_moderation(raw_request_text: str, *, model_name: str | None = None) -> bool:
    """True if `raw_request_text` passes moderation (safe to tutor).

    Uses an in-memory session, never a DB-backed one (research.md §2)
    -- this check is single-shot and has no reason to survive past the
    current invocation.
    """
    resolved_model_name = model_name or os.environ.get(
        "MODERATION_MODEL", "anthropic/claude-haiku-4-5"
    )
    agent = _build_moderation_agent(resolved_model_name)
    session_service = InMemorySessionService()
    runner = Runner(app_name=_APP_NAME, agent=agent, session_service=session_service)
    user_id = "tutor-agent-guardrail"
    session = await session_service.create_session(app_name=_APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text=raw_request_text)])

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if final_text is None:
        # Fail closed, same as the backend's copy of this check.
        return False
    return _ModerationResult.model_validate_json(final_text).allowed


def extract_latest_user_text(llm_request: "LlmRequest") -> str | None:
    """The raw text of the most recent user-role message in `llm_request`.

    This is the JSON-encoded `{question, subject_id, retrieved_passages,
    delegation_context}` payload itself (`agent.py`'s module docstring:
    ADK passes each A2A message's parts through unchanged as the
    Runner's `new_message`), not a parsed/validated object -- guardrails
    below check it as raw text on purpose, since a leaked secret lets an
    attacker put arbitrary content in any field, not just "question".
    """
    for content in reversed(llm_request.contents):
        if content.role != "user" or not content.parts:
            continue
        text = "".join(part.text or "" for part in content.parts)
        if text:
            return text
    return None


async def before_model_guardrail(
    callback_context: "CallbackContext", llm_request: "LlmRequest"
) -> LlmResponse | None:
    """`LlmAgent.before_model_callback` wiring (`agent.py`): runs the
    length cap and moderation re-check before every tutoring model call,
    skipping the model entirely (returning a non-`None` `LlmResponse`) on
    either failure. Returns `None` to let a request through to the actual
    tutoring call.
    """
    del callback_context  # unused -- these checks are stateless
    raw_text = extract_latest_user_text(llm_request)
    if raw_text is None:
        return None

    if not check_length(raw_text):
        return LlmResponse(error_code="request_too_large", error_message="request_too_large")

    if not await check_moderation(raw_text):
        return LlmResponse(error_code="moderation_rejected", error_message="moderation_rejected")

    return None
