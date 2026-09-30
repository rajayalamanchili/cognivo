"""Pre-grading moderation guardrail (spec 007 FR-012, research.md §5).

A lightweight ALLOW/BLOCK classification via Claude Haiku, issued through
the same ADK `LlmAgent` + `LiteLlm` wrapper every other agent call in
this project already uses -- not a new vendor integration. Deliberately a
cheaper/faster model than the Sonnet default used for grading/generation
(research.md §5): moderation is a high-volume, low-complexity
classification task.
"""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types
from pydantic import BaseModel

from src.services.llm_provider import resolve_model

APP_NAME = "cognivo-moderation"

# Bumped whenever _INSTRUCTION's instructional content changes (spec 014
# FR-002/FR-008's CI-enforced version-bump requirement) -- a code
# constant, not a database row, same as GRADING_LOGIC_VERSION.
MODERATION_INSTRUCTION_VERSION = "v1"

_INSTRUCTION = """\
You are a content-moderation classifier for a learning platform's \
free-text answer submissions. Classify the submitted text as allowed or \
blocked.

Block text that contains hate speech, harassment, sexual content, threats \
of violence, or other abusive/toxic content. Do NOT block text merely \
because it is a wrong, off-topic, blank, or nonsensical academic answer -- \
an incorrect or irrelevant answer is a grading concern, not a moderation \
concern.

Respond with ONLY the structured output matching the required schema.
"""


class ModerationResult(BaseModel):
    allowed: bool


class ModerationUnavailableError(Exception):
    """The classifier returned no response -- a service failure, not a
    genuine classification of `text` (spec 026 PR feedback, Principles
    II/V). Callers MUST still fail closed (reject the submission) on
    this, but MUST NOT let a caching layer persist it as if it were a
    real verdict -- unlike a true allow/block result, this carries no
    signal about the submitted text itself, so caching it would
    permanently block that exact text for every learner over one
    transient outage."""


def _build_agent(model_name: str) -> LlmAgent:
    return LlmAgent(
        name="moderation_agent",
        model=LiteLlm(model=model_name),
        instruction=_INSTRUCTION,
        output_schema=ModerationResult,
    )


async def check_moderation(
    text: str,
    *,
    session_service: BaseSessionService,
    model_name: str | None = None,
) -> bool:
    """FR-012: True if `text` passes moderation (safe to grade), False if
    it should be blocked. Raises `ModerationUnavailableError` if the
    classifier returns no response at all -- callers must fail closed on
    that, but it is not itself an allow/block verdict."""
    resolved_model_name = model_name or resolve_model("MODERATION_MODEL", "cheap")
    agent = _build_agent(resolved_model_name)
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    user_id = "moderation-service"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text=text)])

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if final_text is None:
        raise ModerationUnavailableError("no response from the moderation classifier")
    return ModerationResult.model_validate_json(final_text).allowed
