"""Prompted-only misconception classification baseline (spec 013
FR-007, research.md §2) -- the comparison point the fine-tuned
classifier is honestly measured against. Structurally mirrors
`grading-agent/src/guardrails.py`'s `check_moderation()`: a single-shot
ADK `LlmAgent` over an `InMemorySessionService`, no DB session, since
this check has no reason to survive past the current invocation.

Used only by `scripts/check_misconception_classifier_eval.py` -- never
the production classification path (`classify.py`), which never makes
an LLM call at all.
"""

import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

_APP_NAME = "misconception_baseline"

NONE_LABEL = "none"

_INSTRUCTION_TEMPLATE = """\
You are classifying a learner's incorrect free-text answer against a
known list of misconception patterns for this topic.

Question: {question}
Learner's answer: {learner_answer}

Known misconception patterns for this topic:
{taxonomy_lines}

Respond with the misconception_id that best matches the learner's
answer, or "{none_label}" if none of the listed patterns apply.
Respond with ONLY the structured output matching the required schema.
"""


class _BaselineResult(BaseModel):
    misconception_id: str


def _build_instruction(question: str, learner_answer: str, taxonomy: list[dict]) -> str:
    taxonomy_lines = "\n".join(
        f"- {entry['misconception_id']}: {entry['description']}" for entry in taxonomy
    )
    return _INSTRUCTION_TEMPLATE.format(
        question=question,
        learner_answer=learner_answer,
        taxonomy_lines=taxonomy_lines or "(none defined for this topic)",
        none_label=NONE_LABEL,
    )


def _build_agent(model_name: str, instruction: str) -> LlmAgent:
    return LlmAgent(
        name="misconception_baseline",
        model=LiteLlm(model=model_name),
        instruction=instruction,
        output_schema=_BaselineResult,
    )


async def classify_baseline(
    question: str,
    learner_answer: str,
    taxonomy: list[dict],
    *,
    model_name: str | None = None,
) -> str:
    """Returns the baseline's chosen `misconception_id`, or `NONE_LABEL`
    if none of `taxonomy`'s patterns apply. Fails closed to `NONE_LABEL`
    if the model call produces no final response -- same fail-closed
    convention as `check_moderation()`."""
    resolved_model_name = model_name or os.environ.get(
        "MISCONCEPTION_BASELINE_MODEL", "anthropic/claude-haiku-4-5"
    )
    instruction = _build_instruction(question, learner_answer, taxonomy)
    agent = _build_agent(resolved_model_name, instruction)
    session_service = InMemorySessionService()
    runner = Runner(app_name=_APP_NAME, agent=agent, session_service=session_service)
    user_id = "misconception-baseline"
    session = await session_service.create_session(app_name=_APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=[types.Part(text=learner_answer)])

    final_text: str | None = None
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(part.text or "" for part in event.content.parts)

    if final_text is None:
        return NONE_LABEL
    return _BaselineResult.model_validate_json(final_text).misconception_id
